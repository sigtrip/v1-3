"""
biosphere_tools.py — BiosphereTools
Симуляция датчиков и актуаторов для биосферных систем (инкубатор, аквариум,
террариум, теплица).  В реальных условиях заменяется на GPIO/I2C/UART
драйверы через шлюз или напрямую (ESP32/RPi).
"""

import time
import random
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from src.argos_logger import get_logger

log = get_logger("argos.biosphere")


class SensorType(Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    LIGHT = "light"
    SOIL_MOISTURE = "soil_moisture"
    PH = "ph"
    CO2 = "co2"
    WATER_LEVEL = "water_level"
    AMMONIA = "ammonia"
    O2 = "o2"
    UVI = "uvi"


class ActuatorType(Enum):
    HEATER = "heater"
    PUMP = "pump"
    LIGHT = "light"
    FAN = "fan"
    HUMIDIFIER = "humidifier"
    CO2_INJECT = "co2_inject"
    FEEDER = "feeder"
    TURNER = "turner"         # инкубатор — переворачиватель
    MISTER = "mister"         # террариум — туманогенератор
    IRRIGATION = "irrigation"
    SHADE = "shade"


@dataclass
class SensorReading:
    sensor_type: SensorType
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "type": self.sensor_type.value,
            "value": round(self.value, 2),
            "unit": self.unit,
            "ts": self.timestamp,
        }


@dataclass
class ActuatorState:
    actuator_type: ActuatorType
    active: bool = False
    power_pct: int = 100
    last_toggled: float = 0.0

    def to_dict(self) -> dict:
        return {
            "type": self.actuator_type.value,
            "active": self.active,
            "power_pct": self.power_pct,
            "last_toggled": self.last_toggled,
        }


class BiosphereTools:
    """
    Симуляция физического мира для биосферного контроля.

    Поддерживаемые среды:
    - incubator (инкубатор)
    - aquarium (аквариум)
    - terrarium (террариум)
    - greenhouse (теплица)
    - generic (произвольная)

    В production заменяется на реальные драйверы:
    - DHT22/BME280 (temp, humidity)
    - BH1750 (light)
    - PH-4502C (pH)
    - MH-Z19B (CO2)
    - PZEM-004T (power, через PowerSentry)
    """

    ENVIRONMENT_DEFAULTS = {
        "incubator": {
            "temperature_c": 37.5, "humidity_percent": 65.0,
            "co2_ppm": 800, "light_lux": 50,
        },
        "aquarium": {
            "temperature_c": 25.0, "ph": 7.0, "ammonia_ppm": 0.02,
            "o2_ppm": 6.5, "water_level_pct": 95.0, "light_lux": 300,
        },
        "terrarium": {
            "temperature_c": 28.0, "humidity_percent": 70.0,
            "uvi": 3.0, "light_lux": 600,
        },
        "greenhouse": {
            "temperature_c": 22.0, "humidity_percent": 55.0,
            "soil_moisture_pct": 40.0, "co2_ppm": 500, "light_lux": 800,
        },
        "generic": {
            "temperature_c": 22.0, "humidity_percent": 45.0, "light_lux": 150,
        },
    }

    def __init__(self, environment: str = "generic"):
        self.environment = environment
        defaults = self.ENVIRONMENT_DEFAULTS.get(environment,
                                                  self.ENVIRONMENT_DEFAULTS["generic"])
        self.state: Dict[str, float] = dict(defaults)
        self._lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []

        # Актуаторы
        self.actuators: Dict[str, ActuatorState] = {
            "heater": ActuatorState(ActuatorType.HEATER),
            "pump": ActuatorState(ActuatorType.PUMP),
            "light": ActuatorState(ActuatorType.LIGHT),
            "fan": ActuatorState(ActuatorType.FAN),
            "humidifier": ActuatorState(ActuatorType.HUMIDIFIER),
        }

        if environment == "incubator":
            self.actuators["turner"] = ActuatorState(ActuatorType.TURNER)
        if environment == "aquarium":
            self.actuators["co2_inject"] = ActuatorState(ActuatorType.CO2_INJECT)
            self.actuators["feeder"] = ActuatorState(ActuatorType.FEEDER)
        if environment == "terrarium":
            self.actuators["mister"] = ActuatorState(ActuatorType.MISTER)
        if environment == "greenhouse":
            self.actuators["irrigation"] = ActuatorState(ActuatorType.IRRIGATION)
            self.actuators["shade"] = ActuatorState(ActuatorType.SHADE)

        log.info("BiosphereTools: environment=%s, sensors=%d, actuators=%d",
                 environment, len(self.state), len(self.actuators))

    # ── СЕНСОРЫ ───────────────────────────────────────────

    def read_sensor(self, sensor: str) -> Optional[SensorReading]:
        """Считывает показание датчика (с шумом для реализма)."""
        with self._lock:
            key_map = {
                "temperature": ("temperature_c", "°C"),
                "humidity": ("humidity_percent", "%"),
                "light": ("light_lux", "lux"),
                "soil_moisture": ("soil_moisture_pct", "%"),
                "ph": ("ph", "pH"),
                "co2": ("co2_ppm", "ppm"),
                "water_level": ("water_level_pct", "%"),
                "ammonia": ("ammonia_ppm", "ppm"),
                "o2": ("o2_ppm", "ppm"),
                "uvi": ("uvi", "UV index"),
            }
            entry = key_map.get(sensor)
            if not entry:
                return None
            state_key, unit = entry
            raw = self.state.get(state_key)
            if raw is None:
                return None
            # Добавляем шум ±0.5%
            noise = raw * random.uniform(-0.005, 0.005)
            value = raw + noise
            reading = SensorReading(SensorType(sensor), value, unit)
            return reading

    def read_all_sensors(self) -> List[SensorReading]:
        """Считывает все доступные датчики."""
        result = []
        for sensor_name in ["temperature", "humidity", "light", "soil_moisture",
                            "ph", "co2", "water_level", "ammonia", "o2", "uvi"]:
            r = self.read_sensor(sensor_name)
            if r:
                result.append(r)
        return result

    # ── АКТУАТОРЫ ─────────────────────────────────────────

    def toggle(self, actuator_name: str, state: bool, power_pct: int = 100) -> str:
        """Включает/выключает актуатор и симулирует изменение среды."""
        act = self.actuators.get(actuator_name)
        if not act:
            return f"⚠️ Актуатор '{actuator_name}' не найден."

        act.active = state
        act.power_pct = max(0, min(100, power_pct))
        act.last_toggled = time.time()

        # Симуляция воздействия
        with self._lock:
            self._apply_effect(actuator_name, state, power_pct)

        status_str = "ВКЛЮЧЕН" if state else "ВЫКЛЮЧЕН"
        emoji = {"heater": "🔥", "pump": "💧", "light": "☀️", "fan": "💨",
                 "humidifier": "🌫️", "co2_inject": "🫧", "feeder": "🐠",
                 "turner": "🔄", "mister": "💦", "irrigation": "🚿",
                 "shade": "🌥️"}.get(actuator_name, "⚙️")

        msg = f"[{emoji}] {actuator_name} {status_str}"
        if state and power_pct != 100:
            msg += f" ({power_pct}%)"
        log.info(msg)
        self._history.append({"action": actuator_name, "state": state,
                              "power": power_pct, "ts": time.time()})
        return msg

    def _apply_effect(self, name: str, on: bool, pwr: int):
        """Симулирует физическое воздействие актуатора на среду."""
        factor = pwr / 100.0
        if name == "heater":
            delta = 2.0 * factor if on else -0.5
            self.state["temperature_c"] = self.state.get("temperature_c", 22.0) + delta
        elif name == "pump" or name == "irrigation":
            if "humidity_percent" in self.state:
                delta = 10.0 * factor if on else -2.0
                self.state["humidity_percent"] = max(0, min(100,
                    self.state["humidity_percent"] + delta))
            if "soil_moisture_pct" in self.state:
                delta = 8.0 * factor if on else -1.5
                self.state["soil_moisture_pct"] = max(0, min(100,
                    self.state["soil_moisture_pct"] + delta))
        elif name == "light":
            self.state["light_lux"] = int(800 * factor) if on else 50
        elif name == "fan":
            if "temperature_c" in self.state:
                self.state["temperature_c"] -= 1.0 * factor if on else 0
            if "humidity_percent" in self.state:
                self.state["humidity_percent"] -= 3.0 * factor if on else 0
        elif name == "humidifier" or name == "mister":
            if "humidity_percent" in self.state:
                delta = 12.0 * factor if on else -1.0
                self.state["humidity_percent"] = max(0, min(100,
                    self.state["humidity_percent"] + delta))
        elif name == "co2_inject":
            if "co2_ppm" in self.state:
                self.state["co2_ppm"] += 50 * factor if on else 0
        elif name == "feeder":
            if "ammonia_ppm" in self.state:
                self.state["ammonia_ppm"] += 0.01 if on else 0

    # ── СТАТУС ────────────────────────────────────────────

    def get_status(self) -> dict:
        with self._lock:
            sensors = {k: round(v, 2) for k, v in self.state.items()}
        acts = {k: v.to_dict() for k, v in self.actuators.items()}
        return {
            "environment": self.environment,
            "sensors": sensors,
            "actuators": acts,
            "history_len": len(self._history),
        }

    def status(self) -> str:
        """Текстовый отчёт."""
        info = self.get_status()
        lines = [f"🌿 БИОСФЕРА [{self.environment.upper()}]:"]
        lines.append("  Датчики:")
        for k, v in info["sensors"].items():
            lines.append(f"    {k}: {v}")
        lines.append("  Актуаторы:")
        for k, v in info["actuators"].items():
            state_str = "ON" if v["active"] else "off"
            lines.append(f"    {k}: {state_str}")
        return "\n".join(lines)

    def get_history(self, limit: int = 20) -> List[dict]:
        return self._history[-limit:]
