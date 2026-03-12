"""skill_loader.py — загрузчик навыков из src/skills/"""
import os, importlib
from src.argos_logger import get_logger
log = get_logger("argos.skills")

SKILLS_DIR = "src/skills"

class SkillLoader:
    def __init__(self, core=None):
        self.core = core
        self._skills = {}
        self._load_all()

    def _load_all(self):
        for f in os.listdir(SKILLS_DIR):
            if f.endswith(".py") and not f.startswith("__"):
                name = f[:-3]
                try:
                    mod = importlib.import_module(f"src.skills.{name}")
                    self._skills[name] = mod
                except Exception as e:
                    log.warning("Не удалось загрузить навык %s: %s", name, e)
        log.info("Навыков загружено: %d", len(self._skills))

    def dispatch(self, text: str, core=None) -> str | None:
        return None

    def list_skills(self) -> str:
        if not self._skills:
            return "🧬 Навыки не найдены."
        return "🧬 Навыки:\n" + "\n".join(f"  • {s}" for s in sorted(self._skills))
