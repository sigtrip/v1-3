"""
quantum/logic.py — 5 квантовых состояний Аргоса + IBM Quantum Bridge
"""
from __future__ import annotations
import os, time, threading
import psutil
from src.argos_logger import get_logger
log = get_logger("argos.quantum")

STATES = ["Analytic", "Creative", "Protective", "Unstable", "All-Seeing"]

STATE_THRESHOLDS = {
    "Protective": {"cpu": 90, "ram": 90},
    "Unstable":   {"cpu": 75, "ram": 80},
    "All-Seeing": {"cpu": 10, "ram": 30},   # низкая нагрузка = максимальный разум
    "Creative":   {"cpu": 40, "ram": 50},
    "Analytic":   {"cpu": 0,  "ram": 0},
}

class QuantumEngine:
    def __init__(self, core=None):
        self.core  = core
        self.state = "Analytic"
        self._ibm  = None
        self._lock = threading.Lock()
        self._running = False

    def start_auto(self, interval: int = 30):
        self._running = True
        t = threading.Thread(target=self._auto_loop, args=(interval,), daemon=True)
        t.start()
        log.info("QuantumEngine: авто-переключение ON (каждые %d сек)", interval)

    def stop_auto(self):
        self._running = False

    def _auto_loop(self, interval: int):
        while self._running:
            try: self._update_state()
            except Exception as e: log.warning("Quantum auto: %s", e)
            time.sleep(interval)

    def _update_state(self):
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        new = self._select_state(cpu, ram)
        if new != self.state:
            old = self.state
            self.state = new
            log.info("Quantum: %s → %s  (CPU=%.1f%% RAM=%.1f%%)", old, new, cpu, ram)
            if self.core and hasattr(self.core, "context"):
                self.core.context.set_quantum_state(new)

    def _select_state(self, cpu: float, ram: float) -> str:
        if cpu >= STATE_THRESHOLDS["Protective"]["cpu"] or ram >= STATE_THRESHOLDS["Protective"]["ram"]:
            return "Protective"
        if cpu >= STATE_THRESHOLDS["Unstable"]["cpu"] or ram >= STATE_THRESHOLDS["Unstable"]["ram"]:
            return "Unstable"
        if cpu <= STATE_THRESHOLDS["All-Seeing"]["cpu"] and ram <= STATE_THRESHOLDS["All-Seeing"]["ram"]:
            return "All-Seeing"
        if cpu <= STATE_THRESHOLDS["Creative"]["cpu"] and ram <= STATE_THRESHOLDS["Creative"]["ram"]:
            return "Creative"
        return "Analytic"

    def set_state(self, state: str) -> str:
        if state not in STATES:
            return f"❌ Неизвестное состояние: {state}. Доступны: {STATES}"
        self.state = state
        if self.core and hasattr(self.core, "context"):
            self.core.context.set_quantum_state(state)
        return f"⚛️ Квантовое состояние → {state}"

    def get_state(self) -> str:
        cpu = psutil.cpu_percent(interval=0.3)
        ram = psutil.virtual_memory().percent
        return (f"⚛️ Квантовый движок:\n"
                f"  Состояние: {self.state}\n"
                f"  CPU: {cpu:.1f}%  RAM: {ram:.1f}%\n"
                f"  Авто: {self._running}")

    def check_ibm_status(self) -> str:
        if self._ibm is None:
            try:
                from src.quantum.ibm_bridge import IBMQuantumBridge
                self._ibm = IBMQuantumBridge()
            except Exception as e:
                return f"❌ IBM Quantum Bridge: {e}"
        return self._ibm.check_ibm_status()

    def status(self) -> str:
        return self.get_state()
