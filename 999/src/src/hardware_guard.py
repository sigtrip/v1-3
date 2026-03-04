"""
hardware_guard.py — Квантовый гомеостаз железа
  Мониторинг CPU/RAM/температуры и автоматическая стабилизация системы.
"""
import os
import time
import threading
from collections import deque
import psutil

from src.argos_logger import get_logger

log = get_logger("argos.hardware_guard")


class HardwareHomeostasisGuard:
    def __init__(self, core):
        self.core = core
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._last = {
            "cpu": 0.0,
            "ram": 0.0,
            "temp": None,
            "state": "Normal",
            "mitigation": "none",
            "cpu_trend_per_sec": 0.0,
            "cpu_pred_5s": 0.0,
            "ts": 0.0,
        }
        self._cpu_window: deque[tuple[float, float]] = deque(maxlen=64)

        self.interval_sec = max(2, int(os.getenv("ARGOS_HOMEOSTASIS_INTERVAL", "8") or "8"))
        self.protect_cpu = float(os.getenv("ARGOS_HOMEOSTASIS_PROTECT_CPU", "78") or "78")
        self.unstable_cpu = float(os.getenv("ARGOS_HOMEOSTASIS_UNSTABLE_CPU", "92") or "92")
        self.protect_ram = float(os.getenv("ARGOS_HOMEOSTASIS_PROTECT_RAM", "82") or "82")
        self.unstable_ram = float(os.getenv("ARGOS_HOMEOSTASIS_UNSTABLE_RAM", "94") or "94")
        self.protect_temp = float(os.getenv("ARGOS_HOMEOSTASIS_PROTECT_TEMP", "76") or "76")
        self.unstable_temp = float(os.getenv("ARGOS_HOMEOSTASIS_UNSTABLE_TEMP", "86") or "86")

    def start(self) -> str:
        if self._running:
            return "🛡️ Гомеостаз уже активен."
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("Hardware guard: ON")
        return "🛡️ Квантовый гомеостаз активирован."

    def stop(self) -> str:
        self._running = False
        log.info("Hardware guard: OFF")
        return "🛡️ Квантовый гомеостаз отключён."

    def status(self) -> str:
        with self._lock:
            snap = dict(self._last)
        temp_str = "N/A" if snap["temp"] is None else f"{snap['temp']:.1f}°C"
        return (
            "🛡️ КВАНТОВЫЙ ГОМЕОСТАЗ\n"
            f"  Статус: {'🟢 Активен' if self._running else '🔴 Отключён'}\n"
            f"  Состояние: {snap['state']}\n"
            f"  CPU: {snap['cpu']:.1f}% | RAM: {snap['ram']:.1f}% | TEMP: {temp_str}\n"
            f"  CPU тренд: {snap.get('cpu_trend_per_sec', 0.0):+.2f}%/с | Прогноз+5с: {snap.get('cpu_pred_5s', 0.0):.1f}%\n"
            f"  Митигация: {snap['mitigation']}"
        )

    def _loop(self):
        while self._running:
            cpu, ram, temp = self._sample()
            trend_per_sec, cpu_pred_5s = self._update_cpu_trend(cpu)
            state = self._decide_state(cpu, ram, temp, cpu_pred_5s)
            mitigation = self._apply_mitigation(state, cpu, ram, temp)
            with self._lock:
                self._last = {
                    "cpu": cpu,
                    "ram": ram,
                    "temp": temp,
                    "state": state,
                    "mitigation": mitigation,
                    "cpu_trend_per_sec": trend_per_sec,
                    "cpu_pred_5s": cpu_pred_5s,
                    "ts": time.time(),
                }
            time.sleep(self.interval_sec)

    def _update_cpu_trend(self, cpu: float) -> tuple[float, float]:
        now = time.time()
        self._cpu_window.append((now, float(cpu)))
        while self._cpu_window and (now - self._cpu_window[0][0]) > 5.0:
            self._cpu_window.popleft()

        if len(self._cpu_window) < 2:
            return 0.0, float(cpu)

        oldest_ts, oldest_cpu = self._cpu_window[0]
        dt = max(0.001, now - oldest_ts)
        slope = (float(cpu) - oldest_cpu) / dt
        predicted = max(0.0, min(100.0, float(cpu) + slope * 5.0))
        return slope, predicted

    def _sample(self) -> tuple[float, float, float | None]:
        cpu = psutil.cpu_percent(interval=0.25)
        ram = psutil.virtual_memory().percent
        temp = None
        try:
            sensors = psutil.sensors_temperatures() or {}
            vals = []
            for entries in sensors.values():
                for entry in entries:
                    val = getattr(entry, "current", None)
                    if isinstance(val, (int, float)):
                        vals.append(float(val))
            if vals:
                temp = max(vals)
        except Exception:
            temp = None
        return float(cpu), float(ram), temp

    def _decide_state(self, cpu: float, ram: float, temp: float | None, cpu_pred_5s: float) -> str:
        temp_val = temp if temp is not None else 0.0
        unstable = (
            cpu >= self.unstable_cpu or
            ram >= self.unstable_ram or
            (temp is not None and temp_val >= self.unstable_temp)
        )
        if unstable:
            return "Unstable"

        predictive = (
            cpu < self.unstable_cpu and
            cpu_pred_5s >= self.unstable_cpu
        )
        if predictive:
            return "Predictive"

        protective = (
            cpu >= self.protect_cpu or
            ram >= self.protect_ram or
            (temp is not None and temp_val >= self.protect_temp)
        )
        if protective:
            return "Protective"
        return "Analytic"

    def _apply_mitigation(self, state: str, cpu: float, ram: float, temp: float | None) -> str:
        if hasattr(self.core, "quantum") and self.core.quantum:
            try:
                self.core.quantum.set_external_telemetry(cpu=cpu, ram=ram, temp=temp, ttl_seconds=max(10, self.interval_sec * 2))
            except Exception:
                pass

        if state == "Unstable":
            self.core._homeostasis_block_heavy = True
            self.core._homeostasis_preemptive_heavy = False
            self.core.auto_collab_enabled = False
            self.core.auto_collab_max_models = 2
            if hasattr(self.core, "context") and self.core.context:
                self.core.context.set_quantum_state("Unstable")
            if hasattr(self.core, "quantum") and self.core.quantum:
                self.core.quantum.force_state("Unstable", ttl_seconds=max(15, self.interval_sec * 2))
            return "heavy_tasks=blocked, auto_collab=off"

        if state == "Protective":
            self.core._homeostasis_block_heavy = True
            self.core._homeostasis_preemptive_heavy = False
            self.core.auto_collab_enabled = False
            self.core.auto_collab_max_models = 2
            if hasattr(self.core, "context") and self.core.context:
                self.core.context.set_quantum_state("Protective")
            if hasattr(self.core, "quantum") and self.core.quantum:
                self.core.quantum.force_state("Protective", ttl_seconds=max(15, self.interval_sec * 2))
            return "heavy_tasks=throttled, auto_collab=off"

        if state == "Predictive":
            self.core._homeostasis_block_heavy = False
            self.core._homeostasis_preemptive_heavy = True
            self.core.auto_collab_enabled = False
            self.core.auto_collab_max_models = 2
            if hasattr(self.core, "context") and self.core.context:
                self.core.context.set_quantum_state("Protective")
            if hasattr(self.core, "quantum") and self.core.quantum:
                self.core.quantum.force_state("Protective", ttl_seconds=max(10, self.interval_sec * 2))
            return "heavy_tasks=preemptive_offload, auto_collab=off"

        self.core._homeostasis_block_heavy = False
        self.core._homeostasis_preemptive_heavy = False
        if hasattr(self.core, "context") and self.core.context:
            self.core.context.set_quantum_state("Analytic")
        return "none"


# README alias
HardwareGuard = HardwareHomeostasisGuard
