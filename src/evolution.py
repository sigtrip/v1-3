import os
import ast

class ArgosEvolution:
    SKILLS_DIR = "src/skills"

    def apply_patch(self, filename: str, code: str) -> str:
        """Записывает новый навык в src/skills/ после проверки синтаксиса."""
        # 1. Проверка синтаксиса перед записью
        try:
            ast.parse(code)
        except SyntaxError as e:
            return f"❌ Синтаксическая ошибка в коде навыка: {e}"

        # 2. Запись файла
        try:
            os.makedirs(self.SKILLS_DIR, exist_ok=True)
            path = os.path.join(self.SKILLS_DIR, f"{filename}.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            size = os.path.getsize(path)
            return f"✅ Эволюция завершена: {filename} внедрён в ДНК. ({size} байт)"
        except Exception as e:
            return f"❌ Сбой мутации: {e}"

    def list_skills(self) -> str:
        """Возвращает список всех доступных навыков."""
        try:
            files = [f[:-3] for f in os.listdir(self.SKILLS_DIR)
                     if f.endswith(".py") and not f.startswith("__")]
            return "🧬 Навыки в ДНК:\n" + "\n".join(f"  • {s}" for s in sorted(files))
        except Exception as e:
            return f"Ошибка чтения навыков: {e}"

    def remove_skill(self, filename: str) -> str:
        """Удаляет навык из src/skills/."""
        path = os.path.join(self.SKILLS_DIR, f"{filename}.py")
        if not os.path.exists(path):
            return f"❌ Навык '{filename}' не найден."
        os.remove(path)
        return f"🗑️ Навык '{filename}' удалён из ДНК."
