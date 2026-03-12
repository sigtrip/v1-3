"""alert_system.py — Система алертов (CPU/RAM/диск)"""
from __future__ import annotations
import os, time, threading
import psutil
from src.argos_logger import get_logger
log = get_logger("argos.alerts")

class AlertSystem:
    DEFAULT_THRESHOLDS = {"cpu":90.0,"ram":90.0,"disk":95.0}

    def __init__(self, on_alert=None):
        self.on_alert = on_alert
        self.thresholds = dict(self.DEFAULT_THRESHOLDS)
        self._running = False
        self._thread = None
        self._fired: dict[str,float] = {}

    def start(self, interval_sec=30):
        self._running = True
        self._thread = threading.Thread(target=self._loop,
                                        args=(interval_sec,), daemon=True)
        self._thread.start()
        log.info("AlertSystem: ON")

    def stop(self): self._running = False

    def _loop(self, interval):
        while self._running:
            try: self._check()
            except Exception as e: log.warning("Alert check: %s", e)
            time.sleep(interval)

    def _check(self):
        cpu  = psutil.cpu_percent(interval=0.5)
        ram  = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        for name,val in [("cpu",cpu),("ram",ram),("disk",disk)]:
            thr = self.thresholds.get(name,100)
            if val >= thr:
                last = self._fired.get(name,0)
                if time.time()-last > 300:
                    self._fired[name] = time.time()
                    msg = f"⚠️ АЛЕРТ: {name.upper()} = {val:.1f}% (порог {thr}%)"
                    log.warning(msg)
                    if self.on_alert: self.on_alert(name, val, msg)

    def set_threshold(self, name, value) -> str:
        if name not in self.thresholds:
            return f"❌ Неизвестный параметр: {name}"
        self.thresholds[name] = float(value)
        return f"✅ Порог {name}: {value}%"

    def status(self) -> str:
        cpu=psutil.cpu_percent(interval=0.5); ram=psutil.virtual_memory().percent
        disk=psutil.disk_usage("/").percent
        lines = ["⚠️ АЛЕРТЫ:"]
        lines.append(f"  CPU:  {cpu:.1f}% (порог {self.thresholds['cpu']}%)")
        lines.append(f"  RAM:  {ram:.1f}% (порог {self.thresholds['ram']}%)")
        lines.append(f"  Диск: {disk:.1f}% (порог {self.thresholds['disk']}%)")
        lines.append(f"  Активен: {self._running}")
        return "\n".join(lines)
