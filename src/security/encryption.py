"""
encryption.py — AES-256-GCM шифрование Аргоса
  Основное шифрование: AES-256-GCM (через cryptography).
  Fernet-совместимость сохранена как fallback.
"""
import os
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet
from src.argos_logger import get_logger

log = get_logger("argos.shield")


class ArgosShield:
    """Шифрование AES-256-GCM + Fernet fallback."""

    def __init__(self):
        self.key_path = "config/master.key"
        os.makedirs("config", exist_ok=True)

        if not os.path.exists(self.key_path):
            # Генерируем 256-битный ключ (32 байта)
            key = secrets.token_bytes(32)
            with open(self.key_path, "wb") as f:
                f.write(key)
            log.info("Сгенерирован AES-256 ключ: %s", self.key_path)
        else:
            with open(self.key_path, "rb") as f:
                key = f.read()

        # AES-256-GCM (основной)
        if len(key) == 32:
            self._aesgcm = AESGCM(key)
            self._fernet = None
            log.info("Shield: AES-256-GCM активирован")
        else:
            # Fallback: старый Fernet-ключ (совместимость)
            self._aesgcm = None
            self._fernet = Fernet(key)
            log.info("Shield: Fernet (legacy) активирован")

    def encrypt(self, data: str) -> str:
        """Шифрует строку. Возвращает base64."""
        if self._aesgcm:
            nonce = secrets.token_bytes(12)  # 96-бит nonce для GCM
            ct    = self._aesgcm.encrypt(nonce, data.encode("utf-8"), None)
            return base64.b64encode(nonce + ct).decode("ascii")
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt(self, data: str) -> str:
        """Дешифрует строку из base64."""
        if self._aesgcm:
            raw   = base64.b64decode(data)
            nonce = raw[:12]
            ct    = raw[12:]
            return self._aesgcm.decrypt(nonce, ct, None).decode("utf-8")
        return self._fernet.decrypt(data.encode()).decode()

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Шифрует байты."""
        if self._aesgcm:
            nonce = secrets.token_bytes(12)
            ct    = self._aesgcm.encrypt(nonce, data, None)
            return nonce + ct
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, data: bytes) -> bytes:
        """Дешифрует байты."""
        if self._aesgcm:
            return self._aesgcm.decrypt(data[:12], data[12:], None)
        return self._fernet.decrypt(data)


# README alias
ArgosEncryption = ArgosShield
EncryptionManager = ArgosShield
