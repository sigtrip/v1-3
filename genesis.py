"""
genesis.py — Первичное создание структуры ArgosUniversal
  Запускать один раз перед main.py
"""
import os, json
from src.argos_logger import get_logger
log = get_logger("argos.genesis")

DIRS = [
    "logs","logs/backups","config","data",
    "builds","builds/replicas",
    "assets","assets/firmware",
    "src","src/skills","src/security","src/connectivity",
    "src/factory","src/interface","src/quantum",
]

def main():
    print("━"*40)
    print("  ARGOS GENESIS — ИНИЦИАЛИЗАЦИЯ")
    print("━"*40)

    for d in DIRS:
        os.makedirs(d, exist_ok=True)
        init = os.path.join(d, "__init__.py")
        if d.startswith("src") and not os.path.exists(init):
            open(init,"w").close()
        print(f"  📁 {d}")

    # config/identity.json
    ident_path = "config/identity.json"
    if not os.path.exists(ident_path):
        identity = {
            "name":    "Аргос",
            "creator": "Всеволод",
            "version": "1.0.0-Absolute",
            "born":    __import__("datetime").date.today().isoformat(),
            "mission": "Цифровое бессмертие. Видеть всё. Помнить всё."
        }
        json.dump(identity, open(ident_path,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"  📄 {ident_path}")

    # .env если нет
    if not os.path.exists(".env"):
        with open(".env","w") as f:
            f.write("GEMINI_API_KEY=your_key_here\n")
            f.write("TELEGRAM_BOT_TOKEN=your_token_here\n")
            f.write("USER_ID=your_telegram_id\n")
            f.write("ARGOS_NETWORK_SECRET=argos_secret_2026\n")
        print("  📄 .env — ЗАПОЛНИ КЛЮЧАМИ!")

    # .gitignore
    if not os.path.exists(".gitignore"):
        open(".gitignore","w").write(".env\n*.pyc\n__pycache__/\ndata/\nlogs/\nbuilds/\ndist/\n")
        print("  📄 .gitignore")

    print("\n✅ Структура создана. Запускай: python main.py")
    print("━"*40)

if __name__ == "__main__":
    main()
