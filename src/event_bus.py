"""event_bus.py — Шина событий Аргоса"""
from __future__ import annotations
import threading
from collections import defaultdict
from typing import Callable
from src.argos_logger import get_logger
log = get_logger("argos.events")

class EventBus:
    def __init__(self):
        self._subs: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._history: list[dict] = []

    def subscribe(self, topic: str, handler: Callable):
        with self._lock:
            self._subs[topic].append(handler)

    def publish(self, topic: str, data=None):
        with self._lock:
            handlers = list(self._subs.get(topic, []))
            # prefix-match
            for t, hs in self._subs.items():
                if topic.startswith(t) and t != topic:
                    handlers.extend(hs)
        self._history.append({"topic":topic,"data":str(data)[:100]})
        if len(self._history) > 500: self._history = self._history[-500:]
        for h in handlers:
            try: h(topic, data)
            except Exception as e: log.warning("EventBus handler error: %s", e)

    def status(self) -> str:
        with self._lock:
            topics = list(self._subs.keys())
        return (f"🚌 EventBus: {len(topics)} топиков\n"
                f"  Событий в истории: {len(self._history)}\n"
                f"  Топики: {', '.join(topics[:10])}")
