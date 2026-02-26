import serial.tools.list_ports
import time

class AirFlasher:
    def scan_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        return ports if ports else ["Устройства не обнаружены"]

    def flash_air_tag(self, port):
        if port not in self.scan_ports():
            return "Порт недоступен."
        time.sleep(2)  # Эмуляция загрузки микрокода
        return f"Устройство на {port} прошито. Глаза Аргоса открыты."
