"""
jarvis_engine.py — HuggingGPT / JARVIS-inspired task orchestration engine.

Ядро основано на архитектуре microsoft/JARVIS (HuggingGPT):
  1. Task Planning  — LLM парсит запрос в JSON-DAG задач
  2. Model Selection — LLM выбирает оптимальную модель для каждой задачи
  3. Task Execution  — параллельное выполнение с разрешением зависимостей
  4. Response Generation — агрегация результатов в финальный ответ

Адаптировано для Argos: работает с любым бэкендом (Gemini/GigaChat/Ollama/etc),
использует HuggingFace Inference API + локальные модели (LM Studio/Ollama),
интегрируется с существующими инструментами Argos (Tool Calling, Vision, IoT).

License: Apache-2.0 (оригинальный код: microsoft/JARVIS)
"""

import copy
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import requests

from src.argos_logger import get_logger

log = get_logger("argos.jarvis")

# ---------------------------------------------------------------------------
# Промпты (адаптированы из JARVIS/HuggingGPT)
# ---------------------------------------------------------------------------

TASK_PLANNING_SYSTEM = (
    "Ты ИИ-планировщик задач Argos. Пользователь даёт запрос на естественном языке. "
    "Твоя задача — разбить его на атомарные подзадачи и вернуть JSON-массив.\n"
    "Каждая задача: {\"id\": int, \"task\": str, \"args\": dict, \"dep\": [int]}\n"
    "Поле dep содержит id задач-зависимостей (-1 если нет). "
    "task — одна из: text-generation, summarization, translation, "
    "question-answering, text-classification, image-classification, "
    "object-detection, image-to-text, text-to-image, text-to-speech, "
    "automatic-speech-recognition, visual-question-answering, "
    "image-segmentation, depth-estimation, text-to-video, "
    "document-question-answering, conversational, "
    "argos-command, argos-tool-call, argos-vision, argos-iot.\n"
    "Для зависимых ресурсов используй <GENERATED>-id в args.\n"
    "Если запрос тривиальный (обычный разговор), верни [].\n"
    "Отвечай ТОЛЬКО JSON (без markdown, без пояснений)."
)

MODEL_SELECTION_SYSTEM = (
    "Ты ИИ-селектор моделей. Даны задача и список кандидатов. "
    "Выбери лучшую модель и ответь JSON: {\"id\": str, \"reason\": str}. "
    "Учитывай задачу, описание модели, likes и теги. "
    "Отвечай ТОЛЬКО JSON."
)

RESPONSE_SYNTHESIS_SYSTEM = (
    "Ты Аргос — автономная ИИ-система. "
    "Тебе даны результаты выполненных подзадач. "
    "Синтезируй единый связный ответ пользователю на русском языке. "
    "Будь кратким, точным и полезным."
)

# ---------------------------------------------------------------------------
# Конфигурация HuggingFace
# ---------------------------------------------------------------------------

HF_INFERENCE_URL = "https://api-inference.huggingface.co/models"
HF_STATUS_URL = "https://api-inference.huggingface.co/status"

# Маппинг задач на рекомендуемые модели HuggingFace (топ по каждому домену)
DEFAULT_MODELS_MAP: dict[str, list[dict]] = {
    "text-generation": [
        {"id": "meta-llama/Llama-3.2-3B-Instruct", "likes": 500},
        {"id": "microsoft/phi-2", "likes": 400},
    ],
    "summarization": [
        {"id": "facebook/bart-large-cnn", "likes": 2000},
        {"id": "google/pegasus-xsum", "likes": 600},
    ],
    "translation": [
        {"id": "Helsinki-NLP/opus-mt-ru-en", "likes": 300},
        {"id": "Helsinki-NLP/opus-mt-en-ru", "likes": 300},
    ],
    "text-classification": [
        {"id": "cardiffnlp/twitter-roberta-base-sentiment-latest", "likes": 500},
    ],
    "question-answering": [
        {"id": "deepset/roberta-base-squad2", "likes": 800},
    ],
    "image-classification": [
        {"id": "google/vit-base-patch16-224", "likes": 600},
    ],
    "object-detection": [
        {"id": "facebook/detr-resnet-50", "likes": 900},
    ],
    "image-to-text": [
        {"id": "Salesforce/blip-image-captioning-large", "likes": 1200},
    ],
    "text-to-image": [
        {"id": "stabilityai/stable-diffusion-xl-base-1.0", "likes": 5000},
        {"id": "runwayml/stable-diffusion-v1-5", "likes": 8000},
    ],
    "text-to-speech": [
        {"id": "facebook/mms-tts-rus", "likes": 50},
        {"id": "espnet/kan-bayashi_ljspeech_vits", "likes": 200},
    ],
    "automatic-speech-recognition": [
        {"id": "openai/whisper-large-v3", "likes": 3000},
    ],
    "image-segmentation": [
        {"id": "facebook/sam-vit-base", "likes": 1500},
    ],
    "depth-estimation": [
        {"id": "Intel/dpt-large", "likes": 300},
    ],
    "visual-question-answering": [
        {"id": "dandelin/vilt-b32-finetuned-vqa", "likes": 400},
    ],
}


@dataclass
class TaskResult:
    """Результат выполнения одной задачи JARVIS pipeline."""
    task: dict
    choose: dict = field(default_factory=dict)
    inference_result: dict = field(default_factory=dict)


class JarvisEngine:
    """
    HuggingGPT-style orchestration engine для Argos.

    Принимает запрос на естественном языке, декомпозирует на подзадачи,
    выбирает модели, исполняет параллельно с зависимостями,
    синтезирует финальный ответ.
    """

    def __init__(self, core=None):
        self.core = core
        self.hf_token = os.getenv("HUGGINGFACE_TOKEN", "") or os.getenv("HF_TOKEN", "")
        self.hf_headers = {}
        if self.hf_token.startswith("hf_"):
            self.hf_headers = {"Authorization": f"Bearer {self.hf_token}"}
        self.models_map = copy.deepcopy(DEFAULT_MODELS_MAP)
        self.local_endpoint = os.getenv("JARVIS_LOCAL_ENDPOINT", "")
        self.max_parallel = int(os.getenv("JARVIS_MAX_PARALLEL", "4"))
        self.timeout = int(os.getenv("JARVIS_TASK_TIMEOUT", "120"))
        self._results_dir = "public"
        os.makedirs(f"{self._results_dir}/images", exist_ok=True)
        os.makedirs(f"{self._results_dir}/audios", exist_ok=True)
        log.info("JarvisEngine инициализирован (HF token: %s, local: %s)",
                 "✅" if self.hf_token else "❌", self.local_endpoint or "none")

    # ===================================================================
    # PUBLIC API
    # ===================================================================

    def process(self, user_input: str, context: list[dict] | None = None) -> dict:
        """
        Основной pipeline: планирование → выбор моделей → исполнение → синтез.
        Возвращает dict с ключами: message, tasks, results, timing.
        """
        start = time.time()
        context = context or []

        # Stage 1: Task Planning
        tasks = self._plan_tasks(user_input, context)
        if not tasks:
            # Пустые задачи → chitchat
            answer = self._ask_llm(RESPONSE_SYNTHESIS_SYSTEM, user_input)
            return {"message": answer, "tasks": [], "results": {}, "timing": time.time() - start}

        # Для тривиальных NLP задач — прямой ответ
        if len(tasks) == 1 and tasks[0].get("task") in (
            "summarization", "translation", "conversational",
            "text-generation", "text2text-generation"
        ):
            answer = self._ask_llm(RESPONSE_SYNTHESIS_SYSTEM, user_input)
            return {"message": answer, "tasks": tasks, "results": {}, "timing": time.time() - start}

        tasks = self._fix_deps(tasks)
        log.info("Stage 1 — Tasks planned: %d", len(tasks))

        # Stage 2+3: Model Selection + Execution (parallel with deps)
        results = self._execute_tasks(user_input, tasks)
        log.info("Stage 2+3 — Tasks executed: %d results", len(results))

        # Stage 4: Response Synthesis
        answer = self._synthesize_response(user_input, results)
        log.info("Stage 4 — Response synthesized (%.1fs)", time.time() - start)

        return {
            "message": answer,
            "tasks": tasks,
            "results": {k: {"task": v.task, "result": v.inference_result} for k, v in results.items()},
            "timing": time.time() - start,
        }

    def status(self) -> str:
        """Статус движка."""
        hf = "connected" if self.hf_token else "no token"
        local = self.local_endpoint or "none"
        return (
            f"🤖 JARVIS Engine\n"
            f"  HuggingFace: {hf}\n"
            f"  Local models: {local}\n"
            f"  Task types: {len(self.models_map)}\n"
            f"  Max parallel: {self.max_parallel}"
        )

    # ===================================================================
    # STAGE 1: TASK PLANNING
    # ===================================================================

    def _plan_tasks(self, user_input: str, context: list[dict]) -> list[dict]:
        """LLM парсит запрос в JSON-массив задач."""
        prompt = (
            f"Контекст диалога:\n{json.dumps(context[-6:], ensure_ascii=False)}\n\n"
            f"Запрос пользователя: {user_input}\n\n"
            f"Верни JSON-массив задач:"
        )
        raw = self._ask_llm(TASK_PLANNING_SYSTEM, prompt)
        tasks = self._extract_json_array(raw)
        if tasks is None:
            log.warning("Task planning returned non-JSON: %s", raw[:200])
            return []
        # Валидация
        validated = []
        for t in tasks:
            if not isinstance(t, dict):
                continue
            t.setdefault("id", len(validated) + 1)
            t.setdefault("task", "conversational")
            t.setdefault("args", {})
            t.setdefault("dep", [-1])
            validated.append(t)
        return validated

    # ===================================================================
    # STAGE 2: MODEL SELECTION
    # ===================================================================

    def _select_model(self, user_input: str, task: dict) -> dict:
        """LLM выбирает оптимальную модель для задачи."""
        task_type = task.get("task", "")

        # Для Argos-специфичных задач — нет выбора модели
        if task_type.startswith("argos-"):
            return {"id": "argos-internal", "reason": "Built-in Argos capability"}

        candidates = self.models_map.get(task_type, [])
        if not candidates:
            return {"id": "ChatGPT", "reason": f"No specific models for {task_type}, use LLM"}

        if len(candidates) == 1:
            return {"id": candidates[0]["id"], "reason": "Only candidate available"}

        # Проверяем доступность
        available = self._get_available_models(candidates)
        if not available:
            return {"id": "ChatGPT", "reason": "No models available, fall back to LLM"}

        if len(available) == 1:
            return {"id": available[0], "reason": "Only available model"}

        # LLM выбирает
        meta_str = json.dumps([
            {"id": c["id"], "likes": c.get("likes", 0)}
            for c in candidates if c["id"] in available
        ], ensure_ascii=False)
        prompt = (
            f"Задача: {task_type}\n"
            f"Аргументы: {json.dumps(task.get('args', {}), ensure_ascii=False)}\n"
            f"Запрос: {user_input}\n"
            f"Кандидаты: {meta_str}\n"
            f"Выбери лучшую модель. Ответь JSON: {{\"id\": ..., \"reason\": ...}}"
        )
        raw = self._ask_llm(MODEL_SELECTION_SYSTEM, prompt)
        try:
            choice = json.loads(self._find_json_object(raw))
            return choice
        except Exception:
            return {"id": available[0], "reason": "Auto-selected first available"}

    def _get_available_models(self, candidates: list[dict], topk: int = 5) -> list[str]:
        """Проверяет доступность моделей на HuggingFace / локально."""
        available = []
        for c in candidates[:topk]:
            model_id = c["id"]
            # Локальный сервер
            if self.local_endpoint:
                try:
                    r = requests.get(f"{self.local_endpoint}/status/{model_id}", timeout=3)
                    if r.status_code == 200 and r.json().get("loaded"):
                        available.append(model_id)
                        continue
                except Exception:
                    pass
            # HuggingFace
            if self.hf_token:
                try:
                    r = requests.get(
                        f"{HF_STATUS_URL}/{model_id}",
                        headers=self.hf_headers, timeout=5
                    )
                    if r.status_code == 200:
                        state = r.json().get("state", "")
                        if state in ("Loadable", "Loaded"):
                            available.append(model_id)
                except Exception:
                    pass
            # Всегда считаем доступной (для graceful degradation)
            if model_id not in available:
                available.append(model_id)
        return available

    # ===================================================================
    # STAGE 3: TASK EXECUTION
    # ===================================================================

    def _execute_tasks(self, user_input: str, tasks: list[dict]) -> dict[int, TaskResult]:
        """Параллельное выполнение с разрешением зависимостей (JARVIS pattern)."""
        results: dict[int, TaskResult] = {}
        pending = tasks[:]
        threads: list[threading.Thread] = []
        retry = 0

        while pending or any(t.is_alive() for t in threads):
            launched = 0
            for task in pending[:]:
                deps = task.get("dep", [-1])
                # Зависимости разрешены?
                if deps == [-1] or all(d in results for d in deps):
                    if sum(1 for t in threads if t.is_alive()) >= self.max_parallel:
                        break
                    pending.remove(task)
                    t = threading.Thread(
                        target=self._run_single_task,
                        args=(user_input, task, results),
                        daemon=True,
                    )
                    t.start()
                    threads.append(t)
                    launched += 1

            if launched == 0:
                time.sleep(0.3)
                retry += 1
                if retry > self.timeout * 3:
                    log.warning("Execution timeout, breaking (%d pending)", len(pending))
                    break
            else:
                retry = 0

        # Дожидаемся все потоки
        for t in threads:
            t.join(timeout=self.timeout)

        return results

    def _run_single_task(self, user_input: str, task: dict, results: dict):
        """Выполняет одну задачу: выбор модели → инференс → сохранение результата."""
        task_id = task["id"]
        task_type = task.get("task", "")
        args = dict(task.get("args", {}))

        # Подставляем сгенерированные ресурсы из зависимостей
        self._resolve_deps(args, task.get("dep", [-1]), results)
        task["args"] = args

        log.info("Running task %d: %s", task_id, task_type)

        # Argos-native задачи
        if task_type.startswith("argos-"):
            result = self._run_argos_task(task)
            results[task_id] = TaskResult(task=task, choose={"id": "argos"}, inference_result=result)
            return

        # Выбираем модель
        choice = self._select_model(user_input, task)
        model_id = choice.get("id", "ChatGPT")
        log.info("Task %d → model: %s (%s)", task_id, model_id, choice.get("reason", ""))

        # Если ChatGPT/LLM — используем встроенный LLM
        if model_id == "ChatGPT" or model_id == "argos-internal":
            answer = self._ask_llm(
                "user",
                f"Задача: {task_type}, Аргументы: {json.dumps(args, ensure_ascii=False)}. Выполни и дай результат."
            )
            results[task_id] = TaskResult(task=task, choose=choice, inference_result={"response": answer})
            return

        # Инференс через HF API или локально
        inference_result = self._model_inference(model_id, args, task_type)
        results[task_id] = TaskResult(task=task, choose=choice, inference_result=inference_result)

    def _resolve_deps(self, args: dict, deps: list[int], results: dict):
        """Подставляет <GENERATED>-N ссылки на реальные результаты зависимостей."""
        if not deps or deps == [-1]:
            return
        for key, val in list(args.items()):
            if not isinstance(val, str) or "<GENERATED>" not in val:
                continue
            for dep_id in deps:
                if dep_id not in results:
                    continue
                dep_result = results[dep_id].inference_result
                if f"<GENERATED>-{dep_id}" in val:
                    # Подставляем из результата
                    for rkey in ("generated text", "generated image", "generated audio", "response"):
                        if rkey in dep_result:
                            args[key] = dep_result[rkey]
                            break
                elif "<GENERATED>" in val:
                    for rkey in ("generated text", "generated image", "generated audio", "response"):
                        if rkey in dep_result:
                            args[key] = dep_result[rkey]
                            break

    def _run_argos_task(self, task: dict) -> dict:
        """Выполняет Argos-специфичные задачи (команды, vision, IoT)."""
        task_type = task.get("task", "")
        args = task.get("args", {})

        if not self.core:
            return {"error": "ArgosCore not available"}

        if task_type == "argos-command":
            cmd = args.get("command", args.get("text", ""))
            if cmd:
                try:
                    result = self.core.process_logic(cmd, None, None)
                    if isinstance(result, dict):
                        return result
                    return {"response": str(result)}
                except Exception as e:
                    return {"error": str(e)}
            return {"error": "No command specified"}

        if task_type == "argos-vision":
            if self.core.vision:
                try:
                    result = self.core.vision.analyze_screen(args.get("question", "Что на экране?"))
                    return {"response": result}
                except Exception as e:
                    return {"error": str(e)}
            return {"error": "Vision not available"}

        if task_type == "argos-iot":
            if self.core.iot:
                return {"response": self.core.iot.status()}
            return {"error": "IoT not available"}

        if task_type == "argos-tool-call":
            if self.core.tool_calling:
                result = self.core.tool_calling.execute(args.get("text", ""))
                return {"response": str(result)}
            return {"error": "Tool calling not available"}

        return {"error": f"Unknown argos task: {task_type}"}

    def _model_inference(self, model_id: str, data: dict, task: str) -> dict:
        """Маршрутизация инференса: локальный сервер → HuggingFace API."""
        # Попытка локального инференса
        if self.local_endpoint:
            try:
                result = self._local_inference(model_id, data, task)
                if "error" not in result:
                    return result
            except Exception as e:
                log.debug("Local inference failed for %s: %s", model_id, e)

        # HuggingFace Inference API
        if self.hf_token:
            try:
                return self._hf_inference(model_id, data, task)
            except Exception as e:
                log.warning("HF inference failed for %s: %s", model_id, e)
                return {"error": str(e)}

        return {"error": f"No inference backend available for {model_id}"}

    def _local_inference(self, model_id: str, data: dict, task: str) -> dict:
        """Инференс через локальный model server (LM Studio / Ollama / custom)."""
        url = f"{self.local_endpoint}/models/{model_id}"
        r = requests.post(url, json=data, timeout=self.timeout)
        result = r.json()
        # Нормализация путей
        if "path" in result:
            if "image" in task:
                result["generated image"] = result.pop("path")
            elif "audio" in task or "speech" in task:
                result["generated audio"] = result.pop("path")
        return result

    def _hf_inference(self, model_id: str, data: dict, task: str) -> dict:
        """Инференс через HuggingFace Inference API."""
        url = f"{HF_INFERENCE_URL}/{model_id}"

        # NLP задачи
        if task in ("question-answering",):
            payload = {"inputs": {"question": data.get("text", ""), "context": data.get("context", "")}}
            r = requests.post(url, headers=self.hf_headers, json=payload, timeout=self.timeout)
            return r.json()

        if task in ("text-classification", "token-classification", "summarization",
                     "translation", "text-generation", "text2text-generation", "conversational"):
            payload = {"inputs": data.get("text", "")}
            r = requests.post(url, headers=self.hf_headers, json=payload, timeout=self.timeout)
            result = r.json()
            if isinstance(result, list) and result:
                if isinstance(result[0], dict) and "generated_text" in result[0]:
                    return {"generated text": result[0]["generated_text"]}
                if isinstance(result[0], dict) and "summary_text" in result[0]:
                    return {"generated text": result[0]["summary_text"]}
                if isinstance(result[0], dict) and "translation_text" in result[0]:
                    return {"generated text": result[0]["translation_text"]}
            return result if isinstance(result, dict) else {"response": str(result)}

        # Image задачи
        if task == "text-to-image":
            payload = {"inputs": data.get("text", "")}
            r = requests.post(url, headers=self.hf_headers, json=payload, timeout=self.timeout)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                name = str(uuid.uuid4())[:8]
                path = f"{self._results_dir}/images/{name}.png"
                with open(path, "wb") as f:
                    f.write(r.content)
                return {"generated image": path}
            return {"error": f"text-to-image failed: {r.status_code}"}

        if task in ("image-classification", "image-to-text", "object-detection", "image-segmentation"):
            img_url = data.get("image", "")
            if img_url and img_url.startswith("http"):
                img_data = requests.get(img_url, timeout=30).content
            elif img_url and os.path.exists(img_url):
                with open(img_url, "rb") as f:
                    img_data = f.read()
            else:
                return {"error": f"No valid image for {task}"}
            r = requests.post(url, headers=self.hf_headers, data=img_data, timeout=self.timeout)
            return r.json() if r.status_code == 200 else {"error": f"{task} failed: {r.status_code}"}

        # Audio задачи
        if task == "text-to-speech":
            payload = {"inputs": data.get("text", "")}
            r = requests.post(url, headers=self.hf_headers, json=payload, timeout=self.timeout)
            if r.status_code == 200 and "audio" in r.headers.get("content-type", ""):
                name = str(uuid.uuid4())[:8]
                path = f"{self._results_dir}/audios/{name}.flac"
                with open(path, "wb") as f:
                    f.write(r.content)
                return {"generated audio": path}
            return {"error": f"TTS failed: {r.status_code}"}

        if task == "automatic-speech-recognition":
            audio_url = data.get("audio", "")
            if audio_url.startswith("http"):
                audio_data = requests.get(audio_url, timeout=30).content
            elif os.path.exists(audio_url):
                with open(audio_url, "rb") as f:
                    audio_data = f.read()
            else:
                return {"error": "No valid audio for ASR"}
            r = requests.post(url, headers=self.hf_headers, data=audio_data, timeout=self.timeout)
            return r.json() if r.status_code == 200 else {"error": f"ASR failed: {r.status_code}"}

        # Fallback
        payload = data if data else {"inputs": ""}
        r = requests.post(url, headers=self.hf_headers, json=payload, timeout=self.timeout)
        return r.json() if r.status_code == 200 else {"error": f"{task} failed: {r.status_code}"}

    # ===================================================================
    # STAGE 4: RESPONSE SYNTHESIS
    # ===================================================================

    def _synthesize_response(self, user_input: str, results: dict[int, TaskResult]) -> str:
        """Агрегирует результаты всех задач в финальный ответ."""
        if not results:
            return self._ask_llm(RESPONSE_SYNTHESIS_SYSTEM, user_input)

        results_text = []
        for task_id in sorted(results.keys()):
            tr = results[task_id]
            task_type = tr.task.get("task", "unknown")
            model = tr.choose.get("id", "?")
            # Компактный вывод
            result_summary = {}
            for k, v in tr.inference_result.items():
                if isinstance(v, str) and len(v) > 300:
                    result_summary[k] = v[:300] + "..."
                else:
                    result_summary[k] = v
            results_text.append(
                f"Task {task_id} ({task_type}, model: {model}): "
                f"{json.dumps(result_summary, ensure_ascii=False)}"
            )

        prompt = (
            f"Запрос пользователя: {user_input}\n\n"
            f"Результаты выполнения:\n" +
            "\n".join(results_text) +
            "\n\nСинтезируй единый ответ:"
        )
        return self._ask_llm(RESPONSE_SYNTHESIS_SYSTEM, prompt)

    # ===================================================================
    # УТИЛИТЫ
    # ===================================================================

    def _ask_llm(self, system: str, prompt: str) -> str:
        """Вызывает LLM через Argos core (любой доступный бэкенд)."""
        if self.core:
            # Используем ask-chain Argos: gemini → gigachat → ollama → etc.
            for provider_name, provider_fn in self._get_providers():
                try:
                    result = provider_fn(system, prompt)
                    if result and not isinstance(result, dict):
                        return str(result)
                except Exception:
                    continue
        # Fallback: прямой запрос через OpenAI-совместимый API
        return self._ask_llm_fallback(system, prompt)

    def _get_providers(self) -> list[tuple[str, callable]]:
        """Возвращает доступные LLM-провайдеры из Argos core."""
        providers = []
        if not self.core:
            return providers
        # Пробуем методы core в порядке приоритета
        for name, method_name in [
            ("gemini", "_ask_gemini"),
            ("ollama", "_ask_ollama"),
            ("gigachat", "_ask_gigachat"),
            ("yandexgpt", "_ask_yandexgpt"),
            ("openai", "_ask_openai"),
            ("grok", "_ask_grok"),
            ("lmstudio", "_ask_lmstudio"),
            ("watsonx", "_ask_watsonx"),
        ]:
            method = getattr(self.core, method_name, None)
            if method:
                providers.append((name, method))
        return providers

    def _ask_llm_fallback(self, system: str, prompt: str) -> str:
        """Fallback: Gemini REST или Ollama HTTP."""
        # Gemini REST
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                url = os.getenv(
                    "GEMINI_REST_URL",
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                )
                r = requests.post(
                    url,
                    headers={"Content-Type": "application/json", "X-goog-api-key": gemini_key},
                    json={"contents": [{"parts": [{"text": f"{system}\n\n{prompt}"}]}]},
                    timeout=30,
                )
                if r.status_code == 200:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                pass
        # Ollama
        try:
            try:
                ollama_timeout = max(10.0, min(float(os.getenv("ARGOS_OLLAMA_TIMEOUT_SEC", "45") or "45"), 300.0))
            except Exception:
                ollama_timeout = 45.0
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3", "prompt": f"{system}\n\n{prompt}", "stream": False},
                timeout=ollama_timeout,
            )
            r.raise_for_status()
            if r.status_code == 200:
                return r.json().get("response", "")
        except Exception:
            pass
        return f"[JARVIS] Не удалось получить ответ от LLM. Задача: {prompt[:100]}"

    @staticmethod
    def _fix_deps(tasks: list[dict]) -> list[dict]:
        """Исправляет зависимости (порт из JARVIS fix_dep + unfold)."""
        for task in tasks:
            args = task.get("args", {})
            new_deps = []
            for k, v in args.items():
                if isinstance(v, str) and "<GENERATED>" in v:
                    try:
                        dep_id = int(v.split("-")[1])
                        if dep_id not in new_deps:
                            new_deps.append(dep_id)
                    except (IndexError, ValueError):
                        pass
            if new_deps:
                task["dep"] = new_deps
            elif not task.get("dep") or task["dep"] == [0]:
                task["dep"] = [-1]
            # Исправляем циклические зависимости
            task["dep"] = [d for d in task.get("dep", [-1]) if d < task["id"]] or [-1]
        return tasks

    @staticmethod
    def _extract_json_array(text: str) -> list | None:
        """Извлекает JSON-массив из текста LLM."""
        if not text:
            return None
        text = text.strip()
        # Убираем markdown
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()
        # Ищем массив
        start = text.find("[")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    @staticmethod
    def _find_json_object(text: str) -> str:
        """Извлекает JSON-объект из текста."""
        text = text.replace("'", '"')
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end + 1]
        return "{}"
