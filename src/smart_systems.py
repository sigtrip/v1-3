"""smart_systems.py — Оператор умных систем (7 типов)"""
from __future__ import annotations
import json, time
from typing import Callable, Optional
from src.argos_logger import get_logger
log = get_logger("argos.smart")

SYSTEM_PROFILES = {
    "home":        {"name":"Дом",       "sensors":["temp","humidity","co2","motion"],"actuators":["light","heat","ac","lock"]},
    "greenhouse":  {"name":"Теплица",   "sensors":["temp","humidity","soil","light"],"actuators":["water","vent","lamp","heat"]},
    "garage":      {"name":"Гараж",     "sensors":["temp","motion","gas","door"],    "actuators":["door","light","fan","lock"]},
    "cellar":      {"name":"Погреб",    "sensors":["temp","humidity","gas"],         "actuators":["vent","light","heat"]},
    "incubator":   {"name":"Инкубатор", "sensors":["temp","humidity","turn_count"],  "actuators":["heat","humid","fan","turn"]},
    "aquarium":    {"name":"Аквариум",  "sensors":["temp","ph","tds","water_level"], "actuators":["heater","filter","light","pump"]},
    "terrarium":   {"name":"Террариум", "sensors":["temp","humidity","uv"],          "actuators":["heat","light","uv","mist"]},
}

class SmartSystem:
    def __init__(self, sys_type: str, sys_id: str):
        self.sys_type = sys_type
        self.sys_id = sys_id
        self.profile = SYSTEM_PROFILES.get(sys_type, {})
        self.sensors: dict[str,float] = {}
        self.actuators: dict[str,bool] = {}
        self.rules: list[dict] = []
        self.created_at = time.time()
        for s in self.profile.get("sensors",[]): self.sensors[s] = 0.0
        for a in self.profile.get("actuators",[]): self.actuators[a] = False

    def update_sensor(self, name: str, value: float) -> str:
        self.sensors[name] = value
        self._check_rules()
        return f"✅ [{self.sys_id}] {name} = {value}"

    def set_actuator(self, name: str, state: bool) -> str:
        self.actuators[name] = state
        return f"✅ [{self.sys_id}] {name} {'ВКЛ' if state else 'ВЫКЛ'}"

    def add_rule(self, condition: str, action: str) -> str:
        self.rules.append({"condition":condition,"action":action})
        return f"✅ Правило добавлено: если {condition} → {action}"

    def _check_rules(self):
        for rule in self.rules:
            try:
                ctx = {**self.sensors}
                if eval(rule["condition"], {"__builtins__":{}}, ctx):
                    log.info("[%s] Правило сработало: %s", self.sys_id, rule["action"])
            except Exception: pass

    def status(self) -> str:
        lines = [f"🏠 {self.profile.get('name',self.sys_type)} [{self.sys_id}]"]
        lines.append("  Сенсоры: " + ", ".join(f"{k}={v}" for k,v in self.sensors.items()))
        lines.append("  Актуаторы: " + ", ".join(f"{k}={'ON' if v else 'OFF'}" for k,v in self.actuators.items()))
        lines.append(f"  Правил: {len(self.rules)}")
        return "\n".join(lines)

class SmartSystemsManager:
    def __init__(self, on_alert: Optional[Callable]=None):
        self.systems: dict[str, SmartSystem] = {}
        self.on_alert = on_alert

    def add(self, sys_type: str, sys_id: str) -> str:
        if sys_type not in SYSTEM_PROFILES:
            return f"❌ Неизвестный тип: {sys_type}. Доступны: {', '.join(SYSTEM_PROFILES)}"
        self.systems[sys_id] = SmartSystem(sys_type, sys_id)
        return f"✅ Система добавлена: {sys_type} [{sys_id}]"

    def get(self, sys_id: str) -> Optional[SmartSystem]:
        return self.systems.get(sys_id)

    def list_all(self) -> str:
        if not self.systems: return "🏠 Умных систем нет. Добавь: добавь систему [тип] [id]"
        lines = ["🏠 УМНЫЕ СИСТЕМЫ:"]
        for sys in self.systems.values():
            p = sys.profile.get("name", sys.sys_type)
            lines.append(f"  • [{sys.sys_id}] {p} — сенсоров:{len(sys.sensors)} актуаторов:{len(sys.actuators)}")
        return "\n".join(lines)

    def types(self) -> str:
        lines = ["🏠 ТИПЫ УМНЫХ СИСТЕМ:"]
        for k,v in SYSTEM_PROFILES.items():
            lines.append(f"  • {k:12s} — {v['name']}")
            lines.append(f"    Сенсоры: {', '.join(v['sensors'])}")
            lines.append(f"    Актуаторы: {', '.join(v['actuators'])}")
        return "\n".join(lines)
