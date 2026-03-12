"""genesis.py — Первичная настройка Аргоса"""
from __future__ import annotations
import os
from pathlib import Path

ENV_TEMPLATE = """
# ARGOS .env — заполни свои ключи
GEMINI_API_KEY=
TELEGRAM_BOT_TOKEN=
USER_ID=
ARGOS_NETWORK_SECRET=
ARGOS_MASTER_KEY=
PYPI_TOKEN=
PUPI_API_URL=
PUPI_API_TOKEN=
ARGOS_HOMEOSTASIS=on
ARGOS_CURIOSITY=on
ARGOS_LOG_LEVEL=INFO
""".strip()

def main():
    print("🔱 ARGOS Genesis — первичная инициализация\n")
    env_path = Path(".env")
    if env_path.exists():
        print("⚠️  .env уже существует. Пропускаю.")
    else:
        env_path.write_text(ENV_TEMPLATE + "\n")
        print("✅ .env создан — заполни ключи!")

    dirs = ["data","logs","src/skills","src/modules","config/dags",
            "tests/generated","assets/firmware"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("✅ Папки созданы")

    try:
        from src.db_init import init_db
        init_db()
        print("✅ SQLite инициализирована")
    except Exception as e:
        print(f"⚠️  DB: {e}")

    print("\n▶ Теперь запусти: python main.py --no-gui")

if __name__ == "__main__":
    main()
