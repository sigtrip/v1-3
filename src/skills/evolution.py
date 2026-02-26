"""
evolution.py — Модуль саморазвития Аргоса
  Пишет, проверяет и внедряет новые навыки в src/skills/
  Может использовать Gemini для генерации кода навыка.
"""
import os
import ast
import importlib

SKILLS_DIR = "src/skills"


class ArgosEvolution:
    def __init__(self, ai_core=None):
        self.core = ai_core  # ArgosCore для генерации кода

    # ── ЗАПИСЬ НАВЫКА ─────────────────────────────────────
    def apply_patch(self, filename: str, code: str) -> str:
        """Проверяет синтаксис и записывает навык в src/skills/."""
        try:
            ast.parse(code)
        except SyntaxError as e:
            return f"❌ Синтаксическая ошибка: {e}"

        try:
            os.makedirs(SKILLS_DIR, exist_ok=True)
            path = os.path.join(SKILLS_DIR, f"{filename}.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            size = os.path.getsize(path)
            return f"✅ Навык '{filename}' внедрён в ДНК Аргоса ({size} байт)"
        except Exception as e:
            return f"❌ Сбой мутации: {e}"

    # ── ГЕНЕРАЦИЯ КОДА ЧЕРЕЗ ИИ ───────────────────────────
    def generate_skill(self, description: str) -> str:
        """Просит Gemini/Ollama написать код навыка и сохраняет его."""
        if not self.core:
            return "❌ Нет доступа к ядру ИИ. Передай core при инициализации."

        prompt = (
            f"Напиши Python-модуль навыка для ИИ-системы Аргос.\n"
            f"Описание: {description}\n\n"
            f"Требования:\n"
            f"- Один класс с __init__ и методами\n"
            f"- Только стандартные библиотеки + requests + bs4\n"
            f"- Комментарии на русском\n"
            f"- Вернуть только код, без markdown\n"
            f"Имя файла: угадай из описания (snake_case, без .py)"
        )

        answer = self.core._ask_gemini("Ты Python-программист.", prompt)
        if not answer:
            answer = self.core._ask_ollama("Ты Python-программист.", prompt)

        if not answer:
            return "❌ ИИ не ответил. Попробуй позже."

        # Извлекаем имя файла из первой строки комментария
        lines = answer.strip().splitlines()
        filename = "new_skill"
        for line in lines[:3]:
            if line.startswith("#") and ".py" not in line:
                candidate = line.lstrip("#").strip().split()[0].lower()
                if candidate.replace("_","").isalnum():
                    filename = candidate
                    break

        return self.apply_patch(filename, answer)

    # ── УПРАВЛЕНИЕ НАВЫКАМИ ───────────────────────────────
    def list_skills(self) -> str:
        try:
            files = [f[:-3] for f in os.listdir(SKILLS_DIR)
                     if f.endswith(".py") and not f.startswith("__")]
            if not files:
                return "🧬 Навыки не найдены."
            return "🧬 Навыки Аргоса:\n" + "\n".join(f"  • {s}" for s in sorted(files))
        except Exception as e:
            return f"Ошибка: {e}"

    def remove_skill(self, name: str) -> str:
        path = os.path.join(SKILLS_DIR, f"{name}.py")
        if not os.path.exists(path):
            return f"❌ Навык '{name}' не найден."
        os.remove(path)
        return f"🗑️ Навык '{name}' удалён из ДНК."

    def load_skill(self, name: str):
        """Динамически загружает навык по имени."""
        try:
            mod = importlib.import_module(f"src.skills.{name}")
            return mod, f"✅ '{name}' загружен."
        except ModuleNotFoundError:
            return None, f"❌ '{name}' не найден."
