"""
agenticseek_adapter.py — опциональный адаптер к внешнему AgenticSeek backend.

Интеграция сделана через HTTP API (по умолчанию http://127.0.0.1:7777),
без копирования исходников AgenticSeek в этот репозиторий.
"""
from __future__ import annotations

import os
import subprocess
import time
from typing import Tuple

import requests

from src.argos_logger import get_logger

log = get_logger("argos.agenticseek")


class AgenticSeekAdapter:
    def __init__(self):
        base = (os.getenv("ARGOS_AGENTICSEEK_URL", "http://127.0.0.1:7777") or "").strip()
        self.base_url = base.rstrip("/")
        try:
            timeout = float(os.getenv("ARGOS_AGENTICSEEK_TIMEOUT_SEC", "120") or "120")
        except Exception:
            timeout = 120.0
        self.timeout_sec = max(5.0, min(timeout, 600.0))
        self._autostart = (os.getenv("ARGOS_AGENTICSEEK_AUTOSTART", "off") or "off").strip().lower() in {
            "1", "true", "on", "yes", "да", "вкл"
        }
        self._autostart_attempted = False

    def _try_autostart(self):
        if not self._autostart or self._autostart_attempted:
            return
        self._autostart_attempted = True
        try:
            repo_root = os.path.dirname(os.path.dirname(__file__))
            script = os.path.join(repo_root, "scripts", "agenticseek.sh")
            if not os.path.exists(script):
                return
            subprocess.Popen(["bash", script, "start-backend"], cwd=repo_root)
            log.info("Запрошен автозапуск AgenticSeek backend")
        except Exception as e:
            log.warning("Автозапуск AgenticSeek не удался: %s", e)

    def _wait_until_available(self, attempts: int = 8, delay_sec: float = 1.0) -> bool:
        for _ in range(max(1, attempts)):
            try:
                r = requests.get(f"{self.base_url}/health", timeout=3)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(max(0.1, delay_sec))
        return False

    def available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            self._try_autostart()
            if self._autostart:
                return self._wait_until_available()
            return False

    def query(self, prompt: str) -> Tuple[bool, str, str]:
        """Возвращает (ok, answer, error)."""
        payload = {
            "query": prompt,
            "tts_enabled": False,
        }
        try:
            r = requests.post(f"{self.base_url}/query", json=payload, timeout=self.timeout_sec)
            if r.status_code != 200:
                if r.status_code >= 500:
                    return (
                        False,
                        "",
                        "AgenticSeek backend вернул 5xx. Обычно это означает, что не настроен LLM-провайдер "
                        "(например, недоступен Ollama на host.docker.internal:11434) или не заданы API-ключи.",
                    )
                return False, "", f"HTTP {r.status_code}: {r.text[:300]}"

            data = r.json() if r.content else {}
            answer = (data.get("answer") or "").strip()
            if not answer:
                return False, "", "Пустой ответ от AgenticSeek"
            return True, answer, ""
        except Exception as e:
            if self._autostart and self._wait_until_available(attempts=5, delay_sec=1.0):
                try:
                    r2 = requests.post(f"{self.base_url}/query", json=payload, timeout=self.timeout_sec)
                    if r2.status_code == 200:
                        data = r2.json() if r2.content else {}
                        answer = (data.get("answer") or "").strip()
                        if answer:
                            return True, answer, ""
                except Exception:
                    pass
            return False, "", str(e)

    def stop(self) -> None:
        try:
            requests.get(f"{self.base_url}/stop", timeout=5)
        except Exception:
            pass
