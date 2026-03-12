"""observability.py — Метрики и трассировка Аргоса"""
from __future__ import annotations
import time, json, os, threading
from collections import defaultdict, deque
from functools import wraps
from src.argos_logger import get_logger
log = get_logger("argos.obs")

class Metrics:
    _instance = None
    def __new__(cls):
        if not cls._instance: cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self,"_init"): return
        self._init = True
        self._counters: dict[str,int] = defaultdict(int)
        self._gauges:   dict[str,float] = {}
        self._histograms: dict[str,deque] = defaultdict(lambda: deque(maxlen=200))
        self._lock = threading.Lock()
        self._drafter_accept: dict[str,list] = defaultdict(list)

    def inc(self, name, n=1):
        with self._lock: self._counters[name] += n

    def gauge(self, name, value):
        with self._lock: self._gauges[name] = value

    def observe(self, name, value):
        with self._lock: self._histograms[name].append((time.time(), value))

    def record_drafter(self, drafter_id, accepted: bool):
        with self._lock:
            self._drafter_accept[drafter_id].append((time.time(), accepted))

    def get_drafter_acceptance(self, drafter_id) -> float:
        with self._lock:
            recs = self._drafter_accept.get(drafter_id,[])
        if not recs: return 1.0
        accepted = sum(1 for _,a in recs[-50:] if a)
        return accepted / min(len(recs),50)

    def summary(self) -> str:
        with self._lock:
            lines = ["📊 МЕТРИКИ:"]
            for k,v in sorted(self._counters.items()):
                lines.append(f"  {k}: {v}")
            for k,v in sorted(self._gauges.items()):
                lines.append(f"  {k}: {v:.3f}")
            return "\n".join(lines) if len(lines)>1 else "📊 Метрик нет."

_metrics = Metrics()

def trace(name: str):
    """Декоратор трассировки вызовов."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.time()
            try:
                result = fn(*args, **kwargs)
                _metrics.inc(f"trace.{name}.ok")
                _metrics.observe(f"trace.{name}.latency_ms", (time.time()-t0)*1000)
                return result
            except Exception as e:
                _metrics.inc(f"trace.{name}.error")
                raise
        return wrapper
    return decorator

def get_metrics() -> Metrics:
    return _metrics
