import os

from src.argos_logger import get_logger

log = get_logger("argos.gitguard")


class GitGuard:
    def check_security(self):
        """Проверяет защиту секретов. Предупреждает, но не убивает процесс."""
        if not os.path.exists(".gitignore"):
            log.warning("⚠️ .gitignore отсутствует. Риск утечки секретов!")
            # Создаём .gitignore с базовой защитой
            with open(".gitignore", "w") as f:
                f.write(".env\nconfig/master.key\ndata/\nlogs/\n__pycache__/\n*.pyc\n")
            log.info("✅ .gitignore создан с базовой защитой.")
            return
        with open(".gitignore", "r") as f:
            content = f.read()
            if ".env" not in content:
                log.warning("⚠️ .env не защищён в .gitignore! Добавляю...")
                with open(".gitignore", "a") as f2:
                    f2.write("\n.env\nconfig/master.key\n")
                log.info("✅ .env и master.key добавлены в .gitignore.")
            else:
                log.info("✅ Секреты защищены в .gitignore.")
