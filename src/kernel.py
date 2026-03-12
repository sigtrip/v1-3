"""
core.py — Ядро Аргоса v1.3
130+ команд, квантовые состояния, память, агент, навыки.
"""
from __future__ import annotations
import os, subprocess, psutil, platform, time, json, re, threading
from datetime import datetime
from pathlib import Path

from src.argos_logger import get_logger
log = get_logger("argos.core")

class ArgosCore:
    VERSION = "1.3.0"

    def __init__(self):
        self.voice_on = False
        self.operator_mode = False
        self._homeostasis_block_heavy = False
        self._init_quantum()
        self._init_context()
        self._init_memory()
        self._init_scheduler()
        self._init_homeostasis()
        self._init_curiosity()
        self._init_git_ops()
        self._init_pupi()
        self._init_own_model()
        self._init_pypi()
        self._init_skill_loader()
    # Собственная ML-модель
        try:
            from src.argos_model import ArgosOwnModel
            self.own_model = ArgosOwnModel(core=self)
            log.info("Собственная модель: загружена")
        except Exception as e:
            self.own_model = None
            log.warning("Собственная модель недоступна: %s", e)
    
        # PyPI Publisher
        try:
            from src.pypi_publisher import ArgosPyPIPublisher
            self.pypi = ArgosPyPIPublisher(core=self)
            log.info("PyPI Publisher: готов")
        except Exception as e:
            self.pypi = None
            log.warning("PyPI Publisher недоступен: %s", e)

        log.info("ArgosCore v%s готов", self.VERSION)

    # ── ИНИЦИАЛИЗАЦИЯ ПОДСИСТЕМ ──────────────────────────

    def _init_quantum(self):
        try:
            from src.quantum.logic import QuantumEngine
            self.quantum = QuantumEngine()
            log.info("Quantum: OK")
        except Exception as e:
            self.quantum = None
            log.warning("Quantum: %s", e)

    def _init_context(self):
        try:
            from src.context_manager import ArgosContextManager
            self.context = ArgosContextManager()
            log.info("Context: OK")
        except Exception as e:
            self.context = None
            log.warning("Context: %s", e)

    def _init_memory(self):
        try:
            from src.memory import ArgosMemory
            self.memory = ArgosMemory()
            log.info("Memory: OK")
        except Exception as e:
            self.memory = None
            log.warning("Memory: %s", e)

    def _init_scheduler(self):
        try:
            from src.skills.scheduler import ArgosScheduler
            self.scheduler = ArgosScheduler(core=self)
            self.scheduler.start()
            log.info("Scheduler: OK")
        except Exception as e:
            self.scheduler = None
            log.warning("Scheduler: %s", e)

    def _init_homeostasis(self):
        try:
            from src.hardware_guard import HardwareHomeostasisGuard
            self.homeostasis = HardwareHomeostasisGuard(core=self)
            self.homeostasis.start()
            log.info("Homeostasis: OK")
        except Exception as e:
            self.homeostasis = None
            log.warning("Homeostasis: %s", e)

    def _init_curiosity(self):
        try:
            from src.curiosity import ArgosCuriosity
            self.curiosity = ArgosCuriosity(core=self)
            self.curiosity.start()
            log.info("Curiosity: OK")
        except Exception as e:
            self.curiosity = None
            log.warning("Curiosity: %s", e)

    def _init_git_ops(self):
        try:
            from src.git_ops import ArgosGitOps
            self.git_ops = ArgosGitOps()
            log.info("GitOps: OK")
        except Exception as e:
            self.git_ops = None
            log.warning("GitOps: %s", e)

    def _init_pupi(self):
        try:
            from src.pupi_ops import ArgosPupiOps
            self.pupi_ops = ArgosPupiOps()
            log.info("Pupi: OK")
        except Exception as e:
            self.pupi_ops = None
            log.warning("Pupi: %s", e)

    def _init_own_model(self):
        try:
            from src.argos_model import ArgosOwnModel
            self.own_model = ArgosOwnModel(core=self)
            log.info("OwnModel: OK")
        except Exception as e:
            self.own_model = None
            log.warning("OwnModel: %s", e)

    def _init_pypi(self):
        try:
            from src.pypi_publisher import ArgosPyPIPublisher
            self.pypi = ArgosPyPIPublisher(core=self)
            log.info("PyPI: OK")
        except Exception as e:
            self.pypi = None
            log.warning("PyPI: %s", e)

    def _init_skill_loader(self):
        try:
            from src.skill_loader import SkillLoader
            self.skill_loader = SkillLoader(core=self)
            log.info("SkillLoader: OK")
        except Exception as e:
            self.skill_loader = None
            log.warning("SkillLoader: %s", e)

    # ── ГЛАВНЫЙ ДИСПЕТЧЕР ───────────────────────────────

    def process(self, text: str, admin=None, flasher=None) -> dict:
        t = text.lower().strip()

        # Квантовое состояние
        q_data = self.quantum.generate_state() if self.quantum else {"name": "System"}

        # Обновляем любопытство
        if self.curiosity:
            pass
            pass
            self.curiosity.touch_activity(text)

        # Одиночная команда
        intent = self.execute_intent(text, admin, flasher)
        if intent:
            pass
            pass
            return {"answer": intent, "state": q_data["name"]}

        # Навыки
        if self.skill_loader:
            pass
            pass
            skill_answer = self.skill_loader.dispatch(text, core=self)
            if skill_answer:
            pass
            pass
                return {"answer": skill_answer, "state": "Skill"}

        # ИИ-ответ
        ai_answer = self._ask_ai(text, q_data)
        return {"answer": ai_answer, "state": q_data["name"]}

    def _ask_ai(self, text: str, q_data: dict) -> str:
        context = (
            f"Ты Аргос — всевидящий ИИ-ассистент. "
            f"Квантовое состояние: {q_data.get('name', 'System')}. "
            f"Создатель: Всеволод. Год: 2026. Отвечай по-русски."
        )
        gemini = self._ask_gemini(context, text)
        if gemini:
            pass
            pass
            return gemini
        return self._ask_ollama(context + "\n" + text)

    def _ask_gemini(self, system: str, prompt: str) -> str | None:
        key = os.getenv("GEMINI_API_KEY", "")
        if not key:
            pass
            pass
    # ── СОБСТВЕННАЯ МОДЕЛЬ АРГОСА ─────────────────────────
        if self.own_model:
            pass
            pass
            if any(k in t for k in ["модель статус", "model status", "статус модели"]):
            pass
                return self.own_model.status()

            if any(k in t for k in ["модель обучить", "обучи модель", "train model", "model train"]):
            pass
            pass
                return self.own_model.train()

            if any(k in t for k in ["модель сохранить", "сохрани модель", "model save"]):
            pass
            pass
                return self.own_model.save()

            if any(k in t for k in ["модель версия", "model version", "версия модели"]):
            pass
            pass
                return self.own_model.version()

            if any(k in t for k in ["модель история", "model history", "история обучений"]):
            pass
            pass
                return self.own_model.history()

            if any(k in t for k in ["модель экспорт", "model export", "экспорт модели"]):
            pass
            pass
                return self.own_model.export_onnx()

            if t.startswith("модель спросить ") or t.startswith("model ask "):
            pass
            pass
                query = text.split(maxsplit=2)[-1] if len(text.split()) > 2 else ""
                return self.own_model.ask(query) if query else "Формат: модель спросить [вопрос]"

        # ── PYPI PUBLISHER ────────────────────────────────────
        if self.pypi:
            pass
            pass
            if any(k in t for k in ["pypi статус", "пайпи статус", "pypi status"]):
            pass
                return self.pypi.status()

            if any(k in t for k in ["pypi список", "опубликованные навыки", "pypi list"]):
            pass
            pass
                return self.pypi.list_published()

            if t.startswith("pypi опубликовать ") or t.startswith("pypi publish "):
            pass
            pass
                parts = text.split(maxsplit=2)
                skill_name = parts[2] if len(parts) > 2 else ""
                return self.pypi.publish(skill_name) if skill_name else "Формат: pypi опубликовать [skill_name]"

            if t.startswith("pypi собрать ") or t.startswith("pypi build "):
            pass
            pass
                parts = text.split(maxsplit=2)
                skill_name = parts[2] if len(parts) > 2 else ""
                return self.pypi.build_only(skill_name) if skill_name else "Формат: pypi собрать [skill_name]"

            if t.startswith("pypi версия "):
            pass
            pass
                # pypi версия [skill_name] [version]
                parts = text.split(maxsplit=3)
                skill_name = parts[2] if len(parts) > 2 else ""
                version = parts[3] if len(parts) > 3 else None
                return self.pypi.publish(skill_name, version) if skill_name else "Формат: pypi версия [skill_name] [version]"

        return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content(f"{system}\n\n{prompt}")
            return resp.text
        except Exception as e:
            log.warning("Gemini: %s", e)
    # ── СОБСТВЕННАЯ МОДЕЛЬ АРГОСА ─────────────────────────
        if self.own_model:
            pass
            pass
            if any(k in t for k in ["модель статус", "model status", "статус модели"]):
            pass
                return self.own_model.status()

            if any(k in t for k in ["модель обучить", "обучи модель", "train model", "model train"]):
            pass
            pass
                return self.own_model.train()

            if any(k in t for k in ["модель сохранить", "сохрани модель", "model save"]):
            pass
            pass
                return self.own_model.save()

            if any(k in t for k in ["модель версия", "model version", "версия модели"]):
            pass
            pass
                return self.own_model.version()

            if any(k in t for k in ["модель история", "model history", "история обучений"]):
            pass
            pass
                return self.own_model.history()

            if any(k in t for k in ["модель экспорт", "model export", "экспорт модели"]):
            pass
            pass
                return self.own_model.export_onnx()

            if t.startswith("модель спросить ") or t.startswith("model ask "):
            pass
            pass
                query = text.split(maxsplit=2)[-1] if len(text.split()) > 2 else ""
                return self.own_model.ask(query) if query else "Формат: модель спросить [вопрос]"

        # ── PYPI PUBLISHER ────────────────────────────────────
        if self.pypi:
            pass
            pass
            if any(k in t for k in ["pypi статус", "пайпи статус", "pypi status"]):
            pass
                return self.pypi.status()

            if any(k in t for k in ["pypi список", "опубликованные навыки", "pypi list"]):
            pass
            pass
                return self.pypi.list_published()

            if t.startswith("pypi опубликовать ") or t.startswith("pypi publish "):
            pass
            pass
                parts = text.split(maxsplit=2)
                skill_name = parts[2] if len(parts) > 2 else ""
                return self.pypi.publish(skill_name) if skill_name else "Формат: pypi опубликовать [skill_name]"

            if t.startswith("pypi собрать ") or t.startswith("pypi build "):
            pass
            pass
                parts = text.split(maxsplit=2)
                skill_name = parts[2] if len(parts) > 2 else ""
                return self.pypi.build_only(skill_name) if skill_name else "Формат: pypi собрать [skill_name]"

            if t.startswith("pypi версия "):
            pass
            pass
                # pypi версия [skill_name] [version]
                parts = text.split(maxsplit=3)
                skill_name = parts[2] if len(parts) > 2 else ""
                version = parts[3] if len(parts) > 3 else None
                return self.pypi.publish(skill_name, version) if skill_name else "Формат: pypi версия [skill_name] [version]"

        return None

    def _ask_ollama(self, prompt: str) -> str:
        try:
            import requests
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3", "prompt": prompt, "stream": False},
                timeout=30
            )
            return r.json().get("response", "Ollama: пустой ответ")
        except Exception:
            return "⚠️ ИИ-модели недоступны. Настрой GEMINI_API_KEY или запусти Ollama."

    # ── ДИСПЕТЧЕР ИНТЕНТОВ ──────────────────────────────

    def execute_intent(self, text: str, admin=None, flasher=None) -> str | None:
        t = text.lower().strip()

        # Статус системы
        if any(k in t for k in ["статус системы", "чек-ап", "status"]):
            pass
            pass
            return self._system_status()

        # Процессы
        if any(k in t for k in ["список процессов", "процессы", "ps aux"]):
            pass
            pass
            return self._list_processes()

        # Квантовое состояние
        if any(k in t for k in ["квантовое состояние", "quantum status", "⚛️"]):
            pass
            pass
            return self.quantum.status() if self.quantum else "Quantum недоступен"

        # Помощь
        if any(k in t for k in ["помощь", "help", "команды", "что умеешь"]):
            pass
            pass
            return self._help()

        # Git
        if self.git_ops:
            pass
            pass
            if any(k in t for k in ["git статус", "git status"]):
            pass
                return self.git_ops.status()
            if any(k in t for k in ["git пуш", "git push"]):
            pass
            pass
                return self.git_ops.push()
            if t.startswith("git коммит ") or t.startswith("git commit "):
            pass
            pass
                msg = text.split(maxsplit=2)[-1]
                return self.git_ops.commit(msg)
            if any(k in t for k in ["git автокоммит", "git auto push"]):
            pass
            pass
                msg = text.split(maxsplit=3)[-1] if len(text.split()) > 3 else "chore: argos update"
                return self.git_ops.commit_and_push(msg)

        # Собственная модель
        if self.own_model:
            pass
            pass
            if any(k in t for k in ["модель статус", "статус модели"]):
            pass
                return self.own_model.status()
            if any(k in t for k in ["модель обучить", "обучи модель"]):
            pass
            pass
                return self.own_model.train()
            if any(k in t for k in ["модель сохранить"]):
            pass
            pass
                return self.own_model.save()
            if any(k in t for k in ["модель история"]):
            pass
            pass
                return self.own_model.history()
            if any(k in t for k in ["модель версия"]):
            pass
            pass
                return self.own_model.version()
            if t.startswith("модель спросить "):
            pass
            pass
                q = text.split(maxsplit=2)[-1]
                return self.own_model.ask(q)

        # PyPI
        if self.pypi:
            pass
            pass
            if any(k in t for k in ["pypi статус"]):
            pass
                return self.pypi.status()
            if any(k in t for k in ["pypi список"]):
            pass
            pass
                return self.pypi.list_published()
            if t.startswith("pypi опубликовать "):
            pass
            pass
                skill = text.split(maxsplit=2)[-1]
                return self.pypi.publish(skill)
            if t.startswith("pypi собрать "):
            pass
            pass
                skill = text.split(maxsplit=2)[-1]
                return self.pypi.build_only(skill)

        # Память
        if self.memory:
            pass
            pass
            if t.startswith("запомни "):
            pass
                parts = text.split(maxsplit=1)[-1].split("=", 1)
                if len(parts) == 2:
            pass
            pass
                    self.memory.save(parts[0].strip(), parts[1].strip())
                    return f"✅ Запомнил: {parts[0].strip()}"
            if any(k in t for k in ["что ты знаешь", "моя память"]):
            pass
            pass
                return self.memory.summary()

        # Эволюция / навыки
        if t.startswith("создай навык ") or t.startswith("напиши навык "):
            pass
            pass
            from src.skills.evolution.skill import ArgosEvolution
            ev = ArgosEvolution(ai_core=self)
            desc = text.split(maxsplit=2)[-1]
            return ev.generate_skill(desc)

# ── СОБСТВЕННАЯ МОДЕЛЬ АРГОСА ─────────────────────────
        if self.own_model:
            pass
            pass
            if any(k in t for k in ["модель статус", "model status", "статус модели"]):
            pass
                return self.own_model.status()

            if any(k in t for k in ["модель обучить", "обучи модель", "train model", "model train"]):
            pass
            pass
                return self.own_model.train()

            if any(k in t for k in ["модель сохранить", "сохрани модель", "model save"]):
            pass
            pass
                return self.own_model.save()

            if any(k in t for k in ["модель версия", "model version", "версия модели"]):
            pass
            pass
                return self.own_model.version()

            if any(k in t for k in ["модель история", "model history", "история обучений"]):
            pass
            pass
                return self.own_model.history()

            if any(k in t for k in ["модель экспорт", "model export", "экспорт модели"]):
            pass
            pass
                return self.own_model.export_onnx()

            if t.startswith("модель спросить ") or t.startswith("model ask "):
            pass
            pass
                query = text.split(maxsplit=2)[-1] if len(text.split()) > 2 else ""
                return self.own_model.ask(query) if query else "Формат: модель спросить [вопрос]"

        # ── PYPI PUBLISHER ────────────────────────────────────
        if self.pypi:
            pass
            pass
            if any(k in t for k in ["pypi статус", "пайпи статус", "pypi status"]):
            pass
                return self.pypi.status()

            if any(k in t for k in ["pypi список", "опубликованные навыки", "pypi list"]):
            pass
            pass
                return self.pypi.list_published()

            if t.startswith("pypi опубликовать ") or t.startswith("pypi publish "):
            pass
            pass
                parts = text.split(maxsplit=2)
                skill_name = parts[2] if len(parts) > 2 else ""
                return self.pypi.publish(skill_name) if skill_name else "Формат: pypi опубликовать [skill_name]"

            if t.startswith("pypi собрать ") or t.startswith("pypi build "):
            pass
            pass
                parts = text.split(maxsplit=2)
                skill_name = parts[2] if len(parts) > 2 else ""
                return self.pypi.build_only(skill_name) if skill_name else "Формат: pypi собрать [skill_name]"

            if t.startswith("pypi версия "):
            pass
            pass
                # pypi версия [skill_name] [version]
                parts = text.split(maxsplit=3)
                skill_name = parts[2] if len(parts) > 2 else ""
                version = parts[3] if len(parts) > 3 else None
                return self.pypi.publish(skill_name, version) if skill_name else "Формат: pypi версия [skill_name] [version]"

        return None

    # ── СИСТЕМНЫЕ КОМАНДЫ ────────────────────────────────

    def _system_status(self) -> str:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        q = self.quantum.generate_state() if self.quantum else {"name": "N/A"}
        return (
            f"🖥️  СИСТЕМНЫЙ СТАТУС\n"
            f"  CPU:    {cpu:.1f}%\n"
            f"  RAM:    {ram.percent:.1f}% ({ram.used//1024//1024}MB / {ram.total//1024//1024}MB)\n"
            f"  Диск:   {disk.percent:.1f}% ({disk.used//1024//1024//1024}GB / {disk.total//1024//1024//1024}GB)\n"
            f"  ОС:     {platform.system()} {platform.release()}\n"
            f"  ⚛️  Состояние: {q['name']}\n"
            f"  🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _list_processes(self) -> str:
        procs = []
        for p in sorted(psutil.process_iter(["pid","name","cpu_percent","memory_percent"]),
                        key=lambda x: x.info["cpu_percent"] or 0, reverse=True)[:10]:
            i = p.info
            procs.append(f"  {i['pid']:>6} {i['name'][:20]:<20} CPU:{i['cpu_percent'] or 0:>5.1f}%  MEM:{i['memory_percent'] or 0:>5.1f}%")
        return "📋 ТОП ПРОЦЕССОВ:\n" + "\n".join(procs)

    def _help(self) -> str:
        return """🔱 АРГОС — СПИСОК КОМАНД

🖥️  СИСТЕМА
  статус системы · список процессов · квантовое состояние

🧠 ПАМЯТЬ
  запомни [ключ]=[значение] · что ты знаешь

🤖 СОБСТВЕННАЯ МОДЕЛЬ
  модель статус · модель обучить · модель сохранить
  модель спросить [вопрос] · модель история · модель версия

🔁 ЭВОЛЮЦИЯ
  создай навык [описание]

📦 PYPI
  pypi статус · pypi список
  pypi опубликовать [skill] · pypi собрать [skill]

🔧 GIT
  git статус · git коммит [msg] · git пуш · git автокоммит

❓ ПРОЧЕЕ
  помощь — этот список"""

    def say(self, text: str) -> None:
        if not self.voice_on:
            pass
            pass
            return
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
