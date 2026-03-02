"""
master_auth.py — MasterKeyValidator
Авторизация администратора через ARGOS_MASTER_KEY.
SHA-256 comparison, timing-safe, single-instance.
"""

import os
import hmac
import hashlib
import threading
import time
from typing import Optional
from src.argos_logger import get_logger

log = get_logger("argos.auth")


class MasterKeyValidator:
    """
    Безопасная проверка мастер-ключа.

    - Ключ читается из ``ARGOS_MASTER_KEY`` в .env
    - Сравнение через ``hmac.compare_digest`` (constant-time)
    - Лимит: 5 попыток, после чего cooldown 60 с
    - Все события логируются
    """

    MAX_ATTEMPTS: int = 5
    COOLDOWN_SEC: float = 60.0

    def __init__(self):
        self._key: Optional[str] = (os.getenv("ARGOS_MASTER_KEY") or "").strip() or None
        self._lock = threading.Lock()
        self._attempts: int = 0
        self._locked_until: float = 0.0
        self._verified: bool = False
        self._verified_at: float = 0.0

        if not self._key:
            log.warning("ARGOS_MASTER_KEY не задан в .env — авторизация отключена (pass-through)")

    # ── public API ────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """True если ключ задан."""
        return self._key is not None

    @property
    def is_verified(self) -> bool:
        """True если администратор уже прошёл проверку в этой сессии."""
        return self._verified

    def verify(self, user_input: str) -> bool:
        """
        Сравнивает SHA-256 хэши ключей (constant-time).

        Returns:
            True — доступ разрешён, False — отказ.
        """
        if not self._key:
            # Ключ не настроен — bypass
            log.info("Auth bypass: ARGOS_MASTER_KEY не задан.")
            self._verified = True
            self._verified_at = time.time()
            return True

        with self._lock:
            # Проверяем cooldown
            now = time.time()
            if self._locked_until > now:
                remaining = int(self._locked_until - now)
                log.warning("Auth locked: cooldown %d сек", remaining)
                return False

            # Хэшируем
            input_hash = hashlib.sha256(user_input.encode("utf-8")).hexdigest()
            secret_hash = hashlib.sha256(self._key.encode("utf-8")).hexdigest()

            # Constant-time сравнение
            if hmac.compare_digest(input_hash, secret_hash):
                self._verified = True
                self._verified_at = now
                self._attempts = 0
                log.info("[✅] ДОСТУП РАЗРЕШЕН: Администратор подтверждён.")
                return True
            else:
                self._attempts += 1
                log.warning("[❌] ДОСТУП ЗАПРЕЩЁН (попытка %d/%d)",
                            self._attempts, self.MAX_ATTEMPTS)
                if self._attempts >= self.MAX_ATTEMPTS:
                    self._locked_until = now + self.COOLDOWN_SEC
                    log.error("Auth cooldown: %d неудачных попыток → блокировка %ds",
                              self._attempts, int(self.COOLDOWN_SEC))
                return False

    def revoke(self) -> str:
        """Принудительно сбрасывает авторизацию (разлогин)."""
        with self._lock:
            self._verified = False
            self._verified_at = 0.0
            self._attempts = 0
            self._locked_until = 0.0
        log.info("Auth session revoked.")
        return "🔒 Сессия администратора сброшена."

    def status(self) -> str:
        """Текстовый статус авторизации."""
        lines = ["🔐 MASTER AUTH:"]
        lines.append(f"  Ключ задан: {'да' if self._key else 'нет'}")
        lines.append(f"  Верифицирован: {'да' if self._verified else 'нет'}")
        if self._verified_at:
            ago = int(time.time() - self._verified_at)
            lines.append(f"  Авторизован {ago}с назад")
        with self._lock:
            lines.append(f"  Попытки: {self._attempts}/{self.MAX_ATTEMPTS}")
            if self._locked_until > time.time():
                lines.append(f"  ⚠️ Cooldown: ещё {int(self._locked_until - time.time())}с")
        return "\n".join(lines)


# Singleton для импорта
_auth_instance: Optional[MasterKeyValidator] = None
_auth_lock = threading.Lock()


def get_auth() -> MasterKeyValidator:
    """Возвращает singleton MasterKeyValidator."""
    global _auth_instance
    if _auth_instance is None:
        with _auth_lock:
            if _auth_instance is None:
                _auth_instance = MasterKeyValidator()
    return _auth_instance
