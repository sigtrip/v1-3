"""agent.py — Автономные цепочки задач Аргоса"""
from __future__ import annotations
import re, threading, time
from src.argos_logger import get_logger
log = get_logger("argos.agent")

class ArgosAgent:
    def __init__(self, core=None):
        self.core = core
        self._running = False
        self._chain: list[str] = []
        self._results: list[dict] = []
        self._thread: threading.Thread | None = None

    def parse_chain(self, text: str) -> list[str]:
        """Разбирает цепочку задач из текста."""
        # Формат 1: "задача1 → затем задача2 → потом задача3"
        if "→" in text or "затем" in text or "потом" in text:
            parts = re.split(r"→|затем|потом", text, flags=re.I)
            return [p.strip() for p in parts if p.strip()]
        # Формат 2: "1. задача 2. задача 3. задача"
        parts = re.split(r"\d+\.\s*", text)
        return [p.strip() for p in parts if p.strip()]

    def run_chain(self, text: str) -> str:
        chain = self.parse_chain(text)
        if len(chain) < 2:
            return "❌ Укажи цепочку: задача1 → затем задача2"
        self._chain = chain
        self._results = []
        self._running = True
        self._thread = threading.Thread(target=self._execute, daemon=True)
        self._thread.start()
        return (f"🤖 АГЕНТ ЗАПУЩЕН\n"
                f"  Задач: {len(chain)}\n"
                f"  " + "\n  ".join(f"{i+1}. {t}" for i,t in enumerate(chain)) +
                f"\n\n  Статус: отчёт агента")

    def _execute(self):
        for i, task in enumerate(self._chain):
            if not self._running: break
            log.info("Агент: задача %d/%d: %s", i+1, len(self._chain), task)
            result = "N/A"
            if self.core:
                try:
                    r = self.core.process(task)
                    result = r.get("answer","") if isinstance(r,dict) else str(r)
                except Exception as e:
                    result = f"❌ {e}"
            self._results.append({"task":task,"result":result[:200],"step":i+1})
            time.sleep(0.5)
        self._running = False
        log.info("Агент: цепочка завершена (%d задач)", len(self._chain))

    def report(self) -> str:
        if not self._results: return "🤖 Агент: нет выполненных задач."
        lines = [f"🤖 ОТЧЁТ АГЕНТА ({'🔄 работает' if self._running else '✅ завершён'}):"]
        for r in self._results:
            lines.append(f"  {r['step']}. {r['task'][:40]}")
            lines.append(f"     → {r['result'][:100]}")
        return "\n".join(lines)

    def stop(self) -> str:
        self._running = False
        return "🤖 Агент остановлен."

    def status(self) -> str:
        return (f"🤖 Агент: {'работает' if self._running else 'готов'}\n"
                f"  Задач в цепочке: {len(self._chain)}\n"
                f"  Выполнено шагов: {len(self._results)}")
