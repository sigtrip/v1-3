"""
pupi_ops.py — Работа с Pupi API как со скриптовым registry (Git-подобно)
Поддерживает list/pull/push/delete Python-скриптов через HTTP API.
"""

from __future__ import annotations

import os
import requests
from pathlib import Path

from src.argos_logger import get_logger

log = get_logger("argos.pupi")


class ArgosPupiOps:
    def __init__(self):
        self.base_url = (os.getenv("PUPI_API_URL", "") or "").strip().rstrip("/")
        self.token = (os.getenv("PUPI_API_TOKEN", "") or "").strip()
        self.default_branch = (os.getenv("PUPI_BRANCH", "main") or "main").strip() or "main"

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def status(self) -> str:
        if not self.configured:
            return "❌ Pupi API не настроен. Укажи PUPI_API_URL и PUPI_API_TOKEN в .env"
        return (
            "🧰 Pupi API: configured\n"
            f"  URL: {self.base_url}\n"
            f"  Branch: {self.default_branch}"
        )

    def _request(self, method: str, path: str, *, json_payload: dict | None = None) -> tuple[int, dict | str]:
        if not self.configured:
            return 0, "Pupi API not configured"
        url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        try:
            resp = requests.request(method, url, headers=self._headers(), json=json_payload, timeout=25)
            ctype = (resp.headers.get("content-type") or "").lower()
            if "application/json" in ctype:
                body = resp.json()
            else:
                body = (resp.text or "").strip()
            return resp.status_code, body
        except Exception as e:
            log.error("Pupi request error %s %s: %s", method, url, e)
            return -1, str(e)

    def list_scripts(self) -> str:
        code, body = self._request("GET", "/scripts")
        if code <= 0:
            return f"❌ Pupi API недоступен: {body}"
        if code >= 400:
            return f"❌ Pupi API list error: HTTP {code} {body}"

        items = []
        if isinstance(body, dict):
            items = body.get("items") or body.get("scripts") or []
        elif isinstance(body, list):
            items = body

        if not items:
            return "ℹ️ Pupi API: скрипты не найдены."

        lines = [f"🧰 Pupi scripts ({len(items)}):"]
        for it in items[:100]:
            if isinstance(it, dict):
                name = str(it.get("name") or it.get("path") or it.get("id") or "unknown")
                branch = str(it.get("branch") or self.default_branch)
                lines.append(f"  - {name} [{branch}]")
            else:
                lines.append(f"  - {it}")
        return "\n".join(lines)

    def pull_script(self, script_name: str, save_path: str | None = None) -> str:
        name = (script_name or "").strip()
        if not name:
            return "Формат: pupi pull [script_name] [save_path?]"

        code, body = self._request("GET", f"/scripts/{name}")
        if code <= 0:
            return f"❌ Pupi API недоступен: {body}"
        if code >= 400:
            return f"❌ Pupi pull error: HTTP {code} {body}"

        content = ""
        if isinstance(body, dict):
            content = str(body.get("content") or body.get("script") or "")
        elif isinstance(body, str):
            content = body

        if not content:
            return f"❌ Pupi pull: пустой контент для '{name}'"

        if save_path:
            path = Path(save_path)
        else:
            path = Path("src/skills") / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"✅ Pupi pull: '{name}' сохранён в {path.as_posix()}"

    def push_script(self, local_path: str, remote_name: str | None = None) -> str:
        src = Path((local_path or "").strip())
        if not src.exists() or not src.is_file():
            return f"❌ Файл не найден: {src}"

        name = (remote_name or src.stem).strip()
        content = src.read_text(encoding="utf-8")
        payload = {
            "name": name,
            "branch": self.default_branch,
            "content": content,
        }
        code, body = self._request("PUT", f"/scripts/{name}", json_payload=payload)
        if code <= 0:
            return f"❌ Pupi API недоступен: {body}"
        if code >= 400:
            return f"❌ Pupi push error: HTTP {code} {body}"
        return f"✅ Pupi push: '{src.as_posix()}' -> '{name}'"

    def delete_script(self, script_name: str) -> str:
        name = (script_name or "").strip()
        if not name:
            return "Формат: pupi delete [script_name]"

        code, body = self._request("DELETE", f"/scripts/{name}")
        if code <= 0:
            return f"❌ Pupi API недоступен: {body}"
        if code >= 400:
            return f"❌ Pupi delete error: HTTP {code} {body}"
        return f"🗑️ Pupi delete: '{name}' удалён"
