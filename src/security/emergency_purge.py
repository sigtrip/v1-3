"""
emergency_purge.py — Emergency Purge
    Мгновенное уничтожение критических данных одной командой.

    Сценарии:
    - Полная очистка (full): ядро ИИ + логи + память + кэш + конфиги
    - Выборочная (selective): только логи, только кэш, только память
    - Коммуникации (comms): Telegram-токены, P2P-секреты, SSH-ключи
    - Безопасный wipe: перезапись файлов нулями + urandom перед удалением

    ⚠ НЕОБРАТИМАЯ ОПЕРАЦИЯ — требует двухфакторного подтверждения.
    ⚠ Только для защиты СОБСТВЕННЫХ данных администратора.
"""
import os
import re
import sys
import time
import json
import shutil
import secrets
import hashlib
import threading
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from collections import deque
from dataclasses import dataclass, field, asdict

from src.argos_logger import get_logger

log = get_logger("argos.purge")


# ── Enums / Dataclasses ─────────────────────────────────
class PurgeLevel(Enum):
    """Уровень очистки."""
    LOGS = "logs"               # только логи
    CACHE = "cache"             # кэш + временные файлы
    MEMORY = "memory"           # память (SQLite)
    COMMS = "comms"             # ключи/токены/секреты
    SELECTIVE = "selective"     # выборочные пути
    FULL = "full"               # всё вышеперечисленное


class WipeMethod(Enum):
    """Метод затирания."""
    DELETE = "delete"           # обычное удаление
    ZERO = "zero"              # перезапись нулями
    RANDOM = "random"          # перезапись urandom
    DOD = "dod"                # 3 прохода (0x00 → 0xFF → random)


class PurgeStatus(Enum):
    IDLE = "idle"
    PENDING_CONFIRM = "pending_confirm"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PurgeRecord:
    """Запись об операции очистки."""
    ts: float = field(default_factory=time.time)
    level: str = "unknown"
    method: str = "delete"
    files_wiped: int = 0
    bytes_wiped: int = 0
    dirs_removed: int = 0
    duration_sec: float = 0.0
    success: bool = False
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Конфиг путей ─────────────────────────────────────────
_BASE = Path(os.getenv("ARGOS_ROOT", ".")).resolve()

_PURGE_TARGETS = {
    PurgeLevel.LOGS: [
        "logs/",
        "*.log",
    ],
    PurgeLevel.CACHE: [
        "__pycache__/",
        "src/__pycache__/",
        "src/connectivity/__pycache__/",
        "src/security/__pycache__/",
        "src/factory/__pycache__/",
        "data/chroma/",
        "builds/snapshots/",
        ".cache/",
    ],
    PurgeLevel.MEMORY: [
        "data/memory.db",
        "data/memory.db-wal",
        "data/memory.db-shm",
        "data/argos.db",
        "data/argos.db-wal",
        "data/argos.db-shm",
    ],
    PurgeLevel.COMMS: [
        ".env",
        "config/identity.json",
        "config/node_id",
        "config/node_birth",
    ],
}


class EmergencyPurge:
    """
    Emergency Purge — мгновенное уничтожение критических данных.

    Двойное подтверждение:
    1. Команда 'purge [level]' → генерирует одноразовый код
    2. Команда 'подтверди purge [код]' → выполняет очистку

    Методы wipe:
    - delete: обычное удаление (быстро, но восстановимо)
    - zero: перезапись нулями (медленнее, безопаснее)
    - random: перезапись urandom (ещё медленнее, ещё безопаснее)
    - dod: 3 прохода (0x00 → 0xFF → urandom)
    """

    def __init__(self, base_path: Optional[str] = None):
        self._base = Path(base_path).resolve() if base_path else _BASE
        self._lock = threading.Lock()
        self._status = PurgeStatus.IDLE
        self._confirm_code: Optional[str] = None
        self._confirm_expires: float = 0.0
        self._pending_level: Optional[PurgeLevel] = None
        self._pending_method: WipeMethod = WipeMethod.DELETE
        self._pending_targets: List[str] = []
        self._history: deque = deque(maxlen=50)
        self._confirm_timeout = float(os.getenv("ARGOS_PURGE_CONFIRM_SEC", "30"))
        self._enabled = os.getenv("ARGOS_PURGE", "on").strip().lower() not in {
            "0", "false", "off", "no", "нет"
        }
        log.info("EmergencyPurge: base=%s enabled=%s", self._base, self._enabled)

    # ── Публичный API ────────────────────────────────────

    def request_purge(self, level_str: str = "logs",
                      method_str: str = "delete",
                      extra_paths: Optional[List[str]] = None) -> str:
        """
        Инициировать запрос на очистку.
        Возвращает строку с одноразовым кодом подтверждения.
        """
        if not self._enabled:
            return "⛔ Emergency Purge отключён (ARGOS_PURGE=off)."

        with self._lock:
            if self._status == PurgeStatus.IN_PROGRESS:
                return "⚠️ Очистка уже выполняется."

            try:
                level = PurgeLevel(level_str.lower().strip())
            except ValueError:
                valid = ", ".join(l.value for l in PurgeLevel)
                return f"❌ Неизвестный уровень '{level_str}'. Доступные: {valid}"

            try:
                method = WipeMethod(method_str.lower().strip())
            except ValueError:
                valid = ", ".join(m.value for m in WipeMethod)
                return f"❌ Неизвестный метод '{method_str}'. Доступные: {valid}"

            # Подготавливаем список целей
            if level == PurgeLevel.FULL:
                targets = []
                for lvl in [PurgeLevel.LOGS, PurgeLevel.CACHE,
                            PurgeLevel.MEMORY, PurgeLevel.COMMS]:
                    targets.extend(_PURGE_TARGETS.get(lvl, []))
            elif level == PurgeLevel.SELECTIVE:
                targets = extra_paths or []
                if not targets:
                    return "❌ Для selective нужно указать пути: purge selective delete путь1 путь2"
            else:
                targets = list(_PURGE_TARGETS.get(level, []))

            if not targets:
                return "⚠️ Нет целей для очистки."

            # Оценка размера
            total_files, total_bytes = self._estimate(targets)

            # Генерируем код подтверждения
            self._confirm_code = secrets.token_hex(4).upper()
            self._confirm_expires = time.time() + self._confirm_timeout
            self._pending_level = level
            self._pending_method = method
            self._pending_targets = targets
            self._status = PurgeStatus.PENDING_CONFIRM

            log.warning("PURGE REQUEST: level=%s method=%s files≈%d size≈%s code=%s",
                        level.value, method.value, total_files,
                        self._human_size(total_bytes), self._confirm_code)

            return (
                f"⚠️ ЗАПРОС НА ОЧИСТКУ\n"
                f"  Уровень: {level.value}\n"
                f"  Метод: {method.value}\n"
                f"  Файлов ≈ {total_files}\n"
                f"  Размер ≈ {self._human_size(total_bytes)}\n"
                f"  Таймаут: {self._confirm_timeout:.0f}с\n\n"
                f"⚠️ ЭТО НЕОБРАТИМАЯ ОПЕРАЦИЯ!\n"
                f"  Для подтверждения: подтверди purge {self._confirm_code}\n"
                f"  Для отмены: отмени purge"
            )

    def confirm_purge(self, code: str) -> str:
        """Подтвердить очистку одноразовым кодом."""
        with self._lock:
            if self._status != PurgeStatus.PENDING_CONFIRM:
                return "⚠️ Нет ожидающего запроса на очистку."
            if time.time() > self._confirm_expires:
                self._reset_pending()
                return "⏰ Код истёк. Повтори запрос."
            if code.strip().upper() != self._confirm_code:
                return "❌ Неверный код подтверждения."

            self._status = PurgeStatus.IN_PROGRESS

        # Выполняем в фоне (чтобы не блокировать ввод)
        t = threading.Thread(target=self._execute_purge, daemon=True,
                             name="argos-purge")
        t.start()
        return "🔥 Очистка запущена… Следи за статусом: purge статус"

    def cancel_purge(self) -> str:
        """Отменить ожидающий запрос."""
        with self._lock:
            if self._status != PurgeStatus.PENDING_CONFIRM:
                return "ℹ️ Нет ожидающего запроса."
            self._reset_pending()
            return "✅ Запрос на очистку отменён."

    def get_status(self) -> dict:
        """Текущее состояние подсистемы."""
        return {
            "enabled": self._enabled,
            "status": self._status.value,
            "pending_level": self._pending_level.value if self._pending_level else None,
            "pending_method": self._pending_method.value if self._pending_method else None,
            "confirm_code_active": self._confirm_code is not None and time.time() < self._confirm_expires,
            "history_count": len(self._history),
        }

    def status(self) -> str:
        """Человекочитаемый статус."""
        s = self.get_status()
        lines = [
            "🔥 EMERGENCY PURGE",
            f"  Статус: {s['status']}",
            f"  Включён: {'да' if s['enabled'] else 'нет'}",
        ]
        if s["pending_level"]:
            lines.append(f"  Ожидает: {s['pending_level']} ({s['pending_method']})")
        if s["confirm_code_active"]:
            remain = max(0, self._confirm_expires - time.time())
            lines.append(f"  Код действителен: {remain:.0f}с")
        lines.append(f"  История: {s['history_count']} операций")
        if self._history:
            last = self._history[-1]
            lines.append(
                f"  Последняя: {time.strftime('%Y-%m-%d %H:%M', time.localtime(last['ts']))} "
                f"— {last['level']} {'✅' if last['success'] else '❌'}"
            )
        return "\n".join(lines)

    def history(self, limit: int = 10) -> str:
        """История операций очистки."""
        records = list(self._history)[-limit:]
        if not records:
            return "📋 История пуста."
        lines = ["📋 ИСТОРИЯ PURGE:"]
        for r in records:
            dt = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
            ok = "✅" if r["success"] else "❌"
            lines.append(
                f"  {dt} {ok} {r['level']}/{r['method']} — "
                f"{r['files_wiped']} файлов, {self._human_size(r['bytes_wiped'])}, "
                f"{r['duration_sec']:.1f}с"
            )
            if r.get("errors"):
                for e in r["errors"][:3]:
                    lines.append(f"    ⚠ {e[:80]}")
        return "\n".join(lines)

    # ── Внутренняя логика ────────────────────────────────

    def _execute_purge(self):
        """Фактическое выполнение очистки."""
        start = time.time()
        record = PurgeRecord(
            level=self._pending_level.value if self._pending_level else "?",
            method=self._pending_method.value,
        )

        try:
            for target in self._pending_targets:
                full = self._base / target
                if full.is_dir():
                    wiped_f, wiped_b = self._wipe_dir(full, self._pending_method)
                    record.files_wiped += wiped_f
                    record.bytes_wiped += wiped_b
                    record.dirs_removed += 1
                elif full.is_file():
                    sz = full.stat().st_size
                    self._wipe_file(full, self._pending_method)
                    record.files_wiped += 1
                    record.bytes_wiped += sz
                elif "*" in target:
                    # glob-паттерн
                    for p in self._base.glob(target):
                        if p.is_file():
                            sz = p.stat().st_size
                            self._wipe_file(p, self._pending_method)
                            record.files_wiped += 1
                            record.bytes_wiped += sz
                else:
                    record.errors.append(f"Не найден: {target}")

            record.success = True
            log.warning("PURGE COMPLETE: %d files, %s",
                        record.files_wiped, self._human_size(record.bytes_wiped))
        except Exception as exc:
            record.errors.append(str(exc)[:200])
            log.error("PURGE ERROR: %s", exc)
        finally:
            record.duration_sec = round(time.time() - start, 2)
            with self._lock:
                self._history.append(record.to_dict())
                self._status = PurgeStatus.COMPLETED if record.success else PurgeStatus.FAILED
                self._reset_pending()

    def _wipe_file(self, path: Path, method: WipeMethod) -> None:
        """Уничтожить один файл."""
        try:
            sz = path.stat().st_size
            if method == WipeMethod.ZERO and sz > 0:
                with open(path, "wb") as f:
                    f.write(b"\x00" * sz)
            elif method == WipeMethod.RANDOM and sz > 0:
                with open(path, "wb") as f:
                    f.write(os.urandom(sz))
            elif method == WipeMethod.DOD and sz > 0:
                with open(path, "wb") as f:
                    f.write(b"\x00" * sz)
                    f.seek(0)
                    f.write(b"\xff" * sz)
                    f.seek(0)
                    f.write(os.urandom(sz))
            path.unlink(missing_ok=True)
        except Exception as exc:
            log.error("wipe_file %s: %s", path, exc)
            raise

    def _wipe_dir(self, path: Path, method: WipeMethod) -> tuple:
        """Уничтожить директорию. Возвращает (файлов, байт)."""
        total_files = 0
        total_bytes = 0
        if not path.exists():
            return 0, 0
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    sz = child.stat().st_size
                    self._wipe_file(child, method)
                    total_files += 1
                    total_bytes += sz
                except Exception:
                    pass
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass
        return total_files, total_bytes

    def _estimate(self, targets: List[str]) -> tuple:
        """Оценить количество файлов и размер."""
        total_files = 0
        total_bytes = 0
        for target in targets:
            full = self._base / target
            if full.is_dir():
                for child in full.rglob("*"):
                    if child.is_file():
                        try:
                            total_files += 1
                            total_bytes += child.stat().st_size
                        except Exception:
                            pass
            elif full.is_file():
                try:
                    total_files += 1
                    total_bytes += full.stat().st_size
                except Exception:
                    pass
            elif "*" in target:
                for p in self._base.glob(target):
                    if p.is_file():
                        try:
                            total_files += 1
                            total_bytes += p.stat().st_size
                        except Exception:
                            pass
        return total_files, total_bytes

    def _reset_pending(self):
        self._confirm_code = None
        self._confirm_expires = 0.0
        self._pending_level = None
        self._pending_method = WipeMethod.DELETE
        self._pending_targets = []
        if self._status == PurgeStatus.PENDING_CONFIRM:
            self._status = PurgeStatus.IDLE

    @staticmethod
    def _human_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f}{unit}"
            n /= 1024
        return f"{n:.1f}TB"


# ── Singleton ────────────────────────────────────────────
_instance: Optional[EmergencyPurge] = None
_instance_lock = threading.Lock()


def get_emergency_purge(**kwargs) -> EmergencyPurge:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EmergencyPurge(**kwargs)
    return _instance
