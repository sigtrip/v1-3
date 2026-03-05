"""
agent.py — Режим автономного агента Аргоса
  Разбивает сложную задачу на шаги и выполняет цепочку команд.
  "сканируй сеть → найди новые устройства → запиши в файл → отправь в Telegram"
"""

import os
import re
import time

from src.agenticseek_adapter import AgenticSeekAdapter
from src.argos_logger import get_logger

log = get_logger("argos.agent")

STEP_SEPARATORS = [" затем ", " потом ", " после этого ", " → ", "->", " и затем ", " далее "]


class ArgosAgent:
    def __init__(self, core):
        self.core = core
        self._running = False
        self._results = []
        self._agenticseek = AgenticSeekAdapter()

    def _backend_mode(self) -> str:
        mode = (os.getenv("ARGOS_AGENT_BACKEND", "auto") or "auto").strip().lower()
        if mode not in {"auto", "local", "agenticseek"}:
            return "auto"
        return mode

    def _try_agenticseek(self, prompt: str) -> str | None:
        mode = self._backend_mode()
        if mode == "local":
            return None

        strict = (os.getenv("ARGOS_AGENTICSEEK_STRICT", "off") or "off").strip().lower() in {
            "1",
            "true",
            "on",
            "yes",
            "да",
            "вкл",
        }

        if not self._agenticseek.available():
            if mode == "agenticseek" and strict:
                return "❌ AgenticSeek недоступен (/health). Проверь ARGOS_AGENTICSEEK_URL и backend-сервис."
            return None

        ok, answer, err = self._agenticseek.query(prompt)
        if ok:
            self._results = [{"step": "agenticseek", "result": answer[:300], "ok": True}]
            return f"🤖 AgenticSeek:\n\n{answer}"

        log.warning("AgenticSeek ошибка: %s", err)
        if mode == "agenticseek" and strict:
            return f"❌ AgenticSeek ошибка: {err}"
        return None

    def execute_plan(self, plan: str, admin, flasher) -> str:
        """Разбирает план на шаги и выполняет последовательно."""
        ext = self._try_agenticseek(plan)
        if ext:
            return ext

        steps = self._parse_steps(plan)
        if len(steps) <= 1:
            return "Не агентная задача — обычная команда"

        log.info("Агент: %d шагов", len(steps))
        self._results = []
        self._running = True

        results = [f"🤖 АГЕНТ АКТИВИРОВАН — {len(steps)} шагов:\n"]

        for i, step in enumerate(steps, 1):
            if not self._running:
                results.append(f"\n⛔ Выполнение прервано на шаге {i}.")
                break

            step = step.strip()
            if not step:
                continue

            results.append(f"\n📍 Шаг {i}/{len(steps)}: {step}")
            log.info("Шаг %d: %s", i, step)

            try:
                res = self.core.process_logic(step, admin, flasher)
                answer = res.get("answer", "")[:300]
                results.append(f"   ✅ {answer}")
                self._results.append({"step": step, "result": answer, "ok": True})
            except Exception as e:
                err = str(e)
                results.append(f"   ❌ Ошибка: {err}")
                self._results.append({"step": step, "result": err, "ok": False})
                log.error("Шаг %d ошибка: %s", i, err)

            # Небольшая пауза между шагами
            time.sleep(0.5)

        self._running = False
        ok_count = sum(1 for r in self._results if r["ok"])
        fail_count = len(self._results) - ok_count

        results.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━")
        results.append(f"🤖 ПЛАН ВЫПОЛНЕН: ✅ {ok_count} / ❌ {fail_count}")

        return "\n".join(results)

    def _parse_steps(self, text: str) -> list:
        """Разбивает текст на шаги по разделителям."""
        result = [text]
        for sep in STEP_SEPARATORS:
            new_result = []
            for part in result:
                new_result.extend(part.split(sep))
            result = new_result
        # Дополнительно по нумерованным пунктам "1. ... 2. ..."
        numbered = re.split(r"\d+\.\s+", text)
        if len(numbered) > 2:
            return [s.strip() for s in numbered if s.strip()]
        return [s.strip() for s in result if s.strip()]

    def stop(self):
        self._running = False
        if self._backend_mode() in {"auto", "agenticseek"}:
            self._agenticseek.stop()
        return "⛔ Агент остановлен."

    def last_report(self) -> str:
        if not self._results:
            return "📭 Агент ещё не запускался."
        lines = ["📋 ПОСЛЕДНИЙ ОТЧЁТ АГЕНТА:"]
        for i, r in enumerate(self._results, 1):
            icon = "✅" if r["ok"] else "❌"
            lines.append(f"  {icon} Шаг {i}: {r['step'][:50]}")
            lines.append(f"      → {r['result'][:100]}")
        return "\n".join(lines)
