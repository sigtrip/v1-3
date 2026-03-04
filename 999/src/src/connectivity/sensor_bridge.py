import psutil
import platform
import socket
import time
import subprocess

class ArgosSensorBridge:
    def __init__(self):
        self.os_type = platform.system()

    def get_vital_signs(self):
        """Собирает критические показатели 'здоровья' системы."""
        vitals = {
            "battery": self._check_battery(),
            "thermal": self._get_temperature(),
            "network": self._ping_status(),
            "storage": self._disk_health()
        }
        return vitals

    def _check_battery(self):
        """Проверка питания (особенно важно для Android/Laptop нод)."""
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": f"{battery.percent}%",
                "plugged": "Connected" if battery.power_plugged else "Discharging",
                "time_left": f"{battery.secsleft // 60} min" if battery.secsleft != -1 else "Calculating..."
            }
        return "N/A (Stationary Node)"

    def _get_temperature(self):
        """Мониторинг температуры для предотвращения деградации ядер."""
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    main_temp = list(temps.values())[0][0].current
                    return f"{main_temp}°C"
            return "Sensor Hidden"
        except:
            return "Access Denied"

    def _ping_status(self):
        """Задержка связи с глобальными узлами (Latency)."""
        host = "8.8.8.8"
        try:
            start = time.time()
            socket.create_connection((host, 53), timeout=2)
            latency = int((time.time() - start) * 1000)
            status = "Stable" if latency < 100 else "Degraded"
            return {"ping": f"{latency}ms", "status": status}
        except:
            return {"ping": "∞", "status": "Critical (Disconnected)"}

    def _disk_health(self):
        """Проверка свободного места для расширения памяти Аргоса."""
        usage = psutil.disk_usage('/')
        return {
            "free_gb": f"{usage.free // (2**30)} GB",
            "load": f"{usage.percent}%"
        }

    def get_full_report(self):
        """Форматированный отчет для вывода в GUI или Telegram."""
        v = self.get_vital_signs()
        report = (
            f"🩺 [HEALTH REPORT]\n"
            f"• Питание: {v['battery']['percent'] if isinstance(v['battery'], dict) else v['battery']}\n"
            f"• Температура: {v['thermal']}\n"
            f"• Сеть: {v['network']['ping']} ({v['network']['status']})\n"
            f"• Память: {v['storage']['free_gb']} свободно"
        )
        return report


# README alias
SensorBridge = ArgosSensorBridge
