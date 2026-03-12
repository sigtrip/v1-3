"""evolution/skill.py — Саморазвитие Аргоса: создание навыков через ИИ"""
from __future__ import annotations
import ast, os, re, sys, subprocess, importlib, tempfile
from src.argos_logger import get_logger
log = get_logger("argos.evolution")

SKILLS_DIR = "src/skills"
TESTS_DIR  = "tests/generated"

SYSTEM_PROMPT = ("Ты генератор Python-кода для production. "
                 "Запрещено возвращать пояснения, markdown, блоки ```. "
                 "Выводи только валидный, запускаемый Python-модуль.")

class ArgosEvolution:
    def __init__(self, ai_core=None):
        self.core = ai_core

    def _sanitize(self, name: str) -> str:
        raw = re.sub(r"[^a-z0-9_]","_",(name or "new_skill").strip().lower().replace(".py",""))
        return re.sub(r"_+","_",raw).strip("_") or "new_skill"

    def _extract(self, text: str) -> str:
        p = (text or "").strip()
        if p.startswith("```"): p = p.replace("```python","").replace("```","").strip()
        return p

    def _validate(self, code: str) -> tuple[bool,str]:
        if not code.strip(): return False,"пустой код"
        if "```" in code: return False,"markdown fence"
        try:
            tree = ast.parse(code)
        except SyntaxError as e: return False,f"SyntaxError: {e}"
        if not any(isinstance(n,ast.ClassDef) for n in tree.body):
            return False,"нет класса"
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                if node.func.id in {"eval","exec","compile","__import__"}:
                    return False,f"рискованный вызов: {node.func.id}()"
        return True,"ok"

    def _ask_ai(self, prompt: str) -> str | None:
        if not self.core: return None
        return self.core._ask_gemini(SYSTEM_PROMPT, prompt) or self.core._ask_ollama(prompt)

    def generate_skill(self, description: str) -> str:
        if not self.core: return "❌ Нет доступа к ядру ИИ."
        prompt = (f"Напиши Python-модуль навыка для ИИ-системы Аргос.\n"
                  f"Описание: {description}\n"
                  f"Требования: один класс, стандартные библиотеки + requests, комментарии на русском.\n"
                  f"Первая строка комментарий: # имя_файла (snake_case без .py)")
        code = self._extract(self._ask_ai(prompt) or "")
        if not code: return "❌ ИИ не ответил."
        ok,reason = self._validate(code)
        if not ok: return f"❌ Код отклонён: {reason}"
        fname = "new_skill"
        for line in code.splitlines()[:3]:
            if line.startswith("#"):
                candidate = self._sanitize(line.lstrip("#").strip().split()[0])
                if candidate: fname = candidate; break
        return self.apply_patch(fname, code, description=description)

    def apply_patch(self, filename: str, code: str, description: str="") -> str:
        filename = self._sanitize(filename)
        ok,reason = self._validate(code)
        if not ok: return f"❌ Навык отклонён: {reason}"
        os.makedirs(SKILLS_DIR, exist_ok=True)
        path = os.path.join(SKILLS_DIR, f"{filename}.py")
        with open(path,"w",encoding="utf-8") as f: f.write(code)
        size = os.path.getsize(path)
        log.info("Навык создан: %s (%d байт)", path, size)
        return (f"✅ Навык '{filename}' внедрён в ДНК Аргоса ({size} байт).\n"
                f"  Путь: {path}")

    def list_skills(self) -> str:
        try:
            files = [f[:-3] for f in os.listdir(SKILLS_DIR)
                     if f.endswith(".py") and not f.startswith("__")]
            if not files: return "🧬 Навыки не найдены."
            return "🧬 Навыки:\n" + "\n".join(f"  • {s}" for s in sorted(files))
        except Exception as e: return f"❌ {e}"

    def remove_skill(self, name: str) -> str:
        path = os.path.join(SKILLS_DIR, f"{name}.py")
        if not os.path.exists(path): return f"❌ Навык '{name}' не найден."
        os.remove(path)
        return f"🗑️ Навык '{name}' удалён."
