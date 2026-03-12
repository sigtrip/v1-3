"""module_loader.py — Динамический загрузчик модулей"""
from __future__ import annotations
import importlib, inspect, pkgutil
from src.argos_logger import get_logger
from src.modules.base import BaseModule
log = get_logger("argos.modules")

class ModuleLoader:
    def __init__(self, package: str = "src.modules"):
        self.package = package
        self.modules: dict[str, BaseModule] = {}

    def load_all(self, core=None) -> str:
        loaded, errors = [], []
        try:
            pkg = importlib.import_module(self.package)
            for info in pkgutil.iter_modules(pkg.__path__):
                if info.name in {"base","module_loader","__init__"}: continue
                if not info.name.endswith("_module"): continue
                try:
                    py_mod = importlib.import_module(f"{self.package}.{info.name}")
                    for _, obj in inspect.getmembers(py_mod, inspect.isclass):
                        if issubclass(obj, BaseModule) and obj is not BaseModule:
                            inst = obj()
                            if core: inst.setup(core)
                            self.modules[inst.module_id] = inst
                            loaded.append(inst.module_id)
                except Exception as e:
                    errors.append(f"{info.name}: {e}")
        except Exception as e:
            return f"❌ ModuleLoader: {e}"
        lines = [f"🧩 Modules: {len(loaded)} загружено"]
        if loaded: lines.append("  " + ", ".join(sorted(loaded)))
        if errors: lines.extend(f"  ⚠ {e}" for e in errors[:5])
        return "\n".join(lines)

    def dispatch(self, text: str, **kwargs) -> str | None:
        lower = text.lower()
        for mod in self.modules.values():
            try:
                if mod.can_handle(text, lower):
                    return mod.handle(text, lower, **kwargs)
            except Exception as e:
                log.error("Module %s error: %s", mod.module_id, e)
        return None

    def list_modules(self) -> str:
        if not self.modules: return "🧩 Модули не загружены."
        return "🧩 МОДУЛИ:\n" + "\n".join(
            f"  • {m.module_id:16s} — {m.title}"
            for m in sorted(self.modules.values(), key=lambda x: x.module_id))
