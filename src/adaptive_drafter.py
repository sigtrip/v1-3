"""
adaptive_drafter.py — Adaptive Drafter (TLT — Traffic-Light Thinker)
    Интеллектуальная прослойка между пользователем и облачным ИИ:
    - Кэширование ответов (semantic dedup)
    - Сжатие контекста перед отправкой
    - Фильтрация тривиальных запросов (offline-ответ)
    - Учёт лимитов API
"""

import os
import re
import time
import json
import hashlib
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from src.argos_logger import get_logger

log = get_logger("argos.tlt")


class _LRUCache:
    """Thread-safe LRU кэш с TTL."""

    def __init__(self, capacity: int = 512, ttl_sec: float = 3600):
        self._capacity = capacity
        self._ttl = ttl_sec
        self._store: OrderedDict[str, Tuple[float, str]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                self._misses += 1
                return None
            ts, value = item
            if (time.time() - ts) > self._ttl:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = (time.time(), value)
            else:
                if len(self._store) >= self._capacity:
                    self._store.popitem(last=False)
                self._store[key] = (time.time(), value)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "size": len(self._store),
                "capacity": self._capacity,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / max(1, self._hits + self._misses), 3),
            }


class AdaptiveDrafter:
    """
    TLT (Traffic-Light Thinker) — адаптивная прослойка.

    Уровни фильтрации:
    - 🟢 GREEN  — запрос тривиальный, ответ из кэша или оффлайн
    - 🟡 YELLOW — запрос стандартный, сжатие контекста перед отправкой
    - 🔴 RED    — запрос сложный/критический, передаётся ИИ без изменений

    Настройки через ENV:
    - ARGOS_TLT_CACHE_SIZE       (512)
    - ARGOS_TLT_CACHE_TTL        (3600)
    - ARGOS_TLT_COMPRESS_ABOVE   (2000 символов контекста)
    - ARGOS_TLT_OFFLINE_PATTERNS (json-файл с оффлайн-паттернами)
    """

    VERSION = "1.1.0"

    # Встроенные оффлайн-паттерны (GREEN)
    _BUILTIN_OFFLINE = {
        r"^(привет|здравствуй|hi|hello)": "Привет! Чем могу помочь?",
        r"^кто ты": "Я — Аргос, автономная ИИ-система.",
        r"^(время|который час)": "__TIME__",
        r"^(дата|какой сегодня день)": "__DATE__",
        r"^(версия|version)": "__VERSION__",
        r"^спасибо": "Обращайся! 👁️",
        r"^пока|^до свидания|^выход": "До связи! Аргос остаётся на посту. 👁️",
    }

    def __init__(self, core=None):
        self.core = core
        cache_size = int(os.getenv("ARGOS_TLT_CACHE_SIZE", "512") or "512")
        cache_size = max(64, min(512, cache_size))
        cache_ttl = float(os.getenv("ARGOS_TLT_CACHE_TTL", "3600") or "3600")
        self._cache = _LRUCache(capacity=cache_size, ttl_sec=cache_ttl)
        self._compress_threshold = int(os.getenv("ARGOS_TLT_COMPRESS_ABOVE", "2000") or "2000")
        self._compress_max_lines = int(os.getenv("ARGOS_TLT_COMPRESS_MAX_LINES", "80") or "80")
        self._compress_line_limit = int(os.getenv("ARGOS_TLT_COMPRESS_LINE_LIMIT", "280") or "280")
        self._offline_patterns: Dict[str, str] = {}
        self._load_offline_patterns()

        self._total_requests = 0
        self._green_count = 0
        self._yellow_count = 0
        self._red_count = 0
        self._bytes_saved = 0
        self._lock = threading.Lock()

        log.info(
            "TLT v%s init | cache=%d/%ds | compress>%d max_lines=%d",
            self.VERSION,
            cache_size,
            int(cache_ttl),
            self._compress_threshold,
            self._compress_max_lines,
        )

    def _load_offline_patterns(self) -> None:
        """Загружает оффлайн-паттерны: builtin + custom из файла."""
        self._offline_patterns = dict(self._BUILTIN_OFFLINE)
        custom_file = os.getenv("ARGOS_TLT_OFFLINE_PATTERNS", "").strip()
        if custom_file and os.path.isfile(custom_file):
            try:
                with open(custom_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._offline_patterns.update(data)
                    log.info("TLT: загружено %d custom offline patterns", len(data))
            except Exception as e:
                log.warning("TLT: ошибка загрузки offline patterns: %s", e)

    # ── Основной метод ───────────────────────────────────
    def filter(self, query: str, context: str = "") -> Tuple[str, Optional[str]]:
        """
        Оценивает запрос и возвращает (level, response).

        level: "green" | "yellow" | "red"
        response:
            - green  → готовый ответ (str)
            - yellow → None (запрос сжат, нужен ИИ)
            - red    → None (запрос passed-through)
        """
        with self._lock:
            self._total_requests += 1

        q_lower = query.strip().lower()

        # ── GREEN: оффлайн-ответ ─────────────────────────
        for pattern, answer in self._offline_patterns.items():
            if re.search(pattern, q_lower):
                resolved = self._resolve_macro(answer)
                with self._lock:
                    self._green_count += 1
                log.debug("TLT GREEN: '%s' → offline", q_lower[:40])
                return ("green", resolved)

        # ── GREEN: кэш-попадание ─────────────────────────
        cache_key = self._make_key(q_lower, context)
        cached = self._cache.get(cache_key)
        if cached:
            with self._lock:
                self._green_count += 1
            log.debug("TLT GREEN (cache): '%s'", q_lower[:40])
            return ("green", cached)

        # ── YELLOW: контекст > порога → сжатие ───────────
        if len(context) > self._compress_threshold:
            compressed = self._compress_context(context)
            saved = len(context) - len(compressed)
            with self._lock:
                self._yellow_count += 1
                self._bytes_saved += saved
            log.debug("TLT YELLOW: compressed %d → %d (-%d)", len(context), len(compressed), saved)
            return ("yellow", None)

        # ── RED: pass-through ────────────────────────────
        with self._lock:
            self._red_count += 1
        log.debug("TLT RED: pass-through '%s'", q_lower[:40])
        return ("red", None)

    # ── Кэширование ответов ──────────────────────────────
    def cache_response(self, query: str, context: str, response: str) -> None:
        """Сохраняет ответ ИИ в кэш."""
        key = self._make_key(query.strip().lower(), context)
        self._cache.put(key, response)

    def invalidate_cache(self) -> str:
        self._cache.clear()
        return "🧹 TLT: кэш очищен."

    # ── Сжатие контекста ─────────────────────────────────
    def _compress_context(self, context: str) -> str:
        """
        Сжимает контекст: убирает повторы, trailing whitespace,
        обрезает блоки > 500 символов до первых/последних 200.
        """
        lines = context.split("\n")
        seen = set()
        out = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            sig = stripped[:80]
            if sig in seen:
                continue
            seen.add(sig)
            if len(stripped) > self._compress_line_limit:
                head = stripped[: self._compress_line_limit // 2]
                tail = stripped[-(self._compress_line_limit // 2) :]
                stripped = head + " [...] " + tail
            out.append(stripped)
            if len(out) >= self._compress_max_lines:
                break

        if len(out) >= 6:
            head = out[:4]
            tail = out[-2:]
            out = head + ["[...] контекст сжат TLT ..."] + tail
        return "\n".join(out)

    def compress_for_api(self, context: str) -> str:
        """Публичный метод сжатия для использования core.py."""
        if len(context) <= self._compress_threshold:
            return context
        return self._compress_context(context)

    # ── Утилиты ──────────────────────────────────────────
    @staticmethod
    def _make_key(query: str, context: str) -> str:
        raw = f"{query}||{context[:300]}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def _resolve_macro(self, answer: str) -> str:
        if answer == "__TIME__":
            return f"🕐 {time.strftime('%H:%M:%S')}"
        if answer == "__DATE__":
            return f"📅 {time.strftime('%Y-%m-%d, %A')}"
        if answer == "__VERSION__":
            ver = "v1.0.0-Absolute"
            if self.core and hasattr(self.core, "VERSION"):
                ver = self.core.VERSION
            return f"Аргос {ver}"
        return answer

    # ── Статус ───────────────────────────────────────────
    def status(self) -> str:
        cs = self._cache.stats
        with self._lock:
            total = self._total_requests
            g, y, r = self._green_count, self._yellow_count, self._red_count
            saved = self._bytes_saved
        lines = [
            "🚦 TLT (Adaptive Drafter)",
            f"  Версия: {self.VERSION}",
            f"  Запросов: {total} | 🟢 {g} | 🟡 {y} | 🔴 {r}",
            f"  Кэш: {cs['size']}/{cs['capacity']} | hit_rate={cs['hit_rate']:.1%}",
            f"  Сжатие: {saved:,} байт сэкономлено",
            f"  Порог сжатия: {self._compress_threshold} символов",
        ]
        return "\n".join(lines)

    def get_metrics(self) -> dict:
        cs = self._cache.stats
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "green": self._green_count,
                "yellow": self._yellow_count,
                "red": self._red_count,
                "bytes_saved": self._bytes_saved,
                "cache": cs,
            }
