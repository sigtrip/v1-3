"""
biosphere_dag.py — DAG-контроллер биосферы
"""

import logging
import threading
import time

from src.modules.biosphere_tools import ActuatorNode, ClimateAnalyzerNode, SensorReaderNode

log = logging.getLogger("argos.biosphere.dag")


class BiosphereDAGController:
    def __init__(self, core):
        self.core = core
        self.default_profile = {
            "temp_min": 22.0,
            "temp_max": 26.0,
            "hum_min": 60.0,
        }
        self.last_result = ""
        self.last_sys_id = ""
        self._running = False
        self._interval = 30.0
        self._thread = None
        self._auto_sys_id = ""

        # Выстраиваем направленный ациклический граф (конвейер)
        self.pipeline = [
            SensorReaderNode(),
            ClimateAnalyzerNode(),
            ActuatorNode(),
        ]

    def run_cycle(self, sys_id: str, profile: dict) -> str:
        """Прогоняет один полный цикл контроля для указанной биосферы."""
        log.info("🔄 DAG: Старт цикла биосферы '%s'", sys_id)

        # Начальное состояние, которое будет передаваться от узла к узлу
        state = {
            "sys_id": sys_id,
            "profile": profile,
        }

        # Проходим по конвейеру
        for node in self.pipeline:
            state = node.execute(state, self.core)
            if "error" in state:
                log.error("❌ DAG остановлен: %s", state["error"])
                self.last_result = state["error"]
                self.last_sys_id = sys_id
                return state["error"]

        actions = state.get("executed", [])
        self.last_sys_id = sys_id
        if not actions:
            self.last_result = f"🌿 Биосфера '{sys_id}' в идеальном состоянии. Действий не требуется."
            return self.last_result

        self.last_result = f"⚙️ Биосфера '{sys_id}' скорректирована: {', '.join(actions)}"
        return self.last_result

    def set_target(self, key: str, value: float) -> str:
        self.default_profile[key] = float(value)
        return f"🌿 Целевой профиль: {key}={value}"

    def status(self) -> str:
        lines = ["🌿 BIOSPHERE DAG:"]
        lines.append(f"  Автоцикл: {'ON' if self._running else 'OFF'}")
        lines.append(f"  Интервал: {self._interval}s")
        lines.append(f"  Последняя система: {self.last_sys_id or '—'}")
        lines.append(f"  Профиль: {self.default_profile}")
        if self.last_result:
            lines.append(f"  Последний результат: {self.last_result}")
        return "\n".join(lines)

    def get_last_result(self) -> str:
        return self.last_result or "Циклов ещё не было."

    def _loop(self):
        while self._running:
            try:
                if self._auto_sys_id:
                    self.run_cycle(self._auto_sys_id, dict(self.default_profile))
            except Exception as e:
                log.error("Biosphere loop error: %s", e)
            time.sleep(self._interval)

    def start(self, interval_sec: float = 30.0, sys_id: str = "") -> str:
        self._interval = max(2.0, float(interval_sec or 30.0))
        if sys_id:
            self._auto_sys_id = sys_id
        if self._running:
            return f"🌿 BiosphereDAG: уже запущен (каждые {self._interval}с)."
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="biosphere-dag")
        self._thread.start()
        return f"🌿 BiosphereDAG: автоцикл запущен (каждые {self._interval}с)."

    def stop(self) -> str:
        if not self._running:
            return "🌿 BiosphereDAG: не запущен."
        self._running = False
        return "🌿 BiosphereDAG: остановлен."


# Backward compatibility for existing imports
class BiosphereDAG(BiosphereDAGController):
    def __init__(self, environment: str = "generic", core=None, tools=None, targets=None):
        super().__init__(core=core)
        if isinstance(targets, dict):
            self.default_profile.update(targets)
