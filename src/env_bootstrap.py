"""
env_bootstrap.py — единая инициализация переменных окружения Argos.

Гарантирует загрузку .env даже если процесс запущен не из корня репозитория.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import find_dotenv, load_dotenv


def bootstrap_env() -> str | None:
    """Загружает .env и возвращает путь к найденному файлу (или None)."""
    found = find_dotenv(filename=".env", usecwd=True)
    if found:
        load_dotenv(found, override=False)
        return found

    # fallback: корень проекта (родитель src)
    repo_env = Path(__file__).resolve().parent.parent / ".env"
    if repo_env.exists():
        load_dotenv(str(repo_env), override=False)
        return str(repo_env)

    # graceful: ничего не найдено
    return None


def env_value(name: str, default: str | None = None) -> str | None:
    """Утилита безопасного чтения env-переменной."""
    value = os.getenv(name)
    if value is None:
        return default
    return value
