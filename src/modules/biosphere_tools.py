"""
biosphere_tools.py — Инструменты (ноды) для графа управления биосферами
"""

import logging

log = logging.getLogger("argos.biosphere.tools")


class SensorReaderNode:
    """Узел 1: Сбор телеметрии с датчиков биосферы."""

    def execute(self, state, core):
        sys_id = state.get("sys_id")
        if not sys_id or not core.smart_sys or sys_id not in core.smart_sys.systems:
            return {"error": f"Система '{sys_id}' не найдена или smart_sys отключен."}

        system = core.smart_sys.systems[sys_id]
        state["sensor_data"] = system.sensors
        log.info("🌿 Сбор данных [%s]: %s", sys_id, system.sensors)
        return state


class ClimateAnalyzerNode:
    """Узел 2: Принятие решений (AI/Logic) на основе профиля идеальной среды."""

    def execute(self, state, core):
        if "error" in state:
            return state

        data = state.get("sensor_data", {})
        profile = state.get("profile", {})
        actions = []

        # Парсим текущие значения (по умолчанию 0, если датчик молчит)
        temp = float(data.get("temp", 0))
        hum = float(data.get("humidity", 0))

        # Берем целевые рамки из профиля
        target_temp_min = profile.get("temp_min", 22.0)
        target_temp_max = profile.get("temp_max", 26.0)
        target_hum_min = profile.get("hum_min", 60.0)

        # Логика терморегуляции
        if temp < target_temp_min and temp != 0:
            actions.append(("heater", "on"))
            actions.append(("fan", "off"))
        elif temp > target_temp_max:
            actions.append(("heater", "off"))
            actions.append(("fan", "on"))
        else:
            actions.append(("heater", "off"))
            actions.append(("fan", "off"))

        # Логика влажности/полива
        if hum < target_hum_min and hum != 0:
            actions.append(("irrigation", "on"))  # Или humidifier
        else:
            actions.append(("irrigation", "off"))

        state["planned_actions"] = actions
        return state


class ActuatorNode:
    """Узел 3: Отправка команд на реле и IoT-устройства."""

    def execute(self, state, core):
        if "error" in state:
            return state

        sys_id = state.get("sys_id")
        actions = state.get("planned_actions", [])

        executed = []
        for actuator, command in actions:
            # Отправляем команду через встроенный Smart Systems менеджер
            core.smart_sys.command(sys_id, actuator, command)
            executed.append(f"{actuator}={command}")

        log.info("⚙️ Исполнение [%s]: %s", sys_id, ", ".join(executed) if executed else "В норме")
        state["executed"] = executed
        return state


# README alias
class BiosphereTools:
    """Facade for biosphere pipeline nodes."""

    SensorReader = SensorReaderNode
    ClimateAnalyzer = ClimateAnalyzerNode
    Actuator = ActuatorNode
