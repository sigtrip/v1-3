import os, sys

class GitGuard:
    def check_security(self):
        if not os.path.exists(".gitignore"):
            print("[FATAL]: .gitignore отсутствует. Риск утечки Аргоса!")
            sys.exit(1)
        with open(".gitignore", "r") as f:
            if ".env" not in f.read():
                print("[FATAL]: .env не защищен! Блокировка запуска.")
                sys.exit(1)
