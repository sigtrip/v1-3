"""
usb_diagnostics.py — USB-диагностика авторизованных устройств
  Подключение к Arduino/ESP/STM32 для прошивки и отладки.
  Поддержка: Serial, CDC, HID (только собственные устройства).

  Сценарии использования:
  - Прошивка IoT-устройств через USB-C смартфона
  - Чтение логов и отладочной информации
  - Конфигурирование устройств
"""

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from src.argos_logger import get_logger
    from src.event_bus import Events, get_bus
    from src.observability import trace
except ImportError:
    import logging

    get_logger = lambda name: logging.getLogger(name)
    get_bus = lambda: None
    Events = type("Events", (), {})()
    trace = lambda name: lambda f: f

log = get_logger("argos.usb")

# Путь к базе авторизованных устройств
USB_DEVICES_FILE = "data/usb_authorized.json"


class DeviceType(Enum):
    """Тип USB-устройства."""

    ARDUINO_UNO = "arduino_uno"
    ARDUINO_NANO = "arduino_nano"
    ARDUINO_MEGA = "arduino_mega"
    ESP8266 = "esp8266"
    ESP32 = "esp32"
    STM32 = "stm32"
    RP2040 = "rp2040"
    GENERIC_SERIAL = "generic_serial"
    UNKNOWN = "unknown"


class ConnectionMode(Enum):
    """Режим подключения."""

    SERIAL = "serial"
    CDC = "cdc"
    HID = "hid"


@dataclass
class AuthorizedDevice:
    """Авторизованное USB-устройство."""

    vid: str  # Vendor ID (hex)
    pid: str  # Product ID (hex)
    serial: str  # Серийный номер
    name: str  # Человекочитаемое имя
    device_type: str  # Тип устройства
    baudrate: int  # Скорость подключения
    authorized_at: float  # Время авторизации
    last_connected: float  # Последнее подключение
    notes: str = ""  # Заметки

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AuthorizedDevice":
        return cls(**d)

    @property
    def device_id(self) -> str:
        """Уникальный идентификатор устройства."""
        return f"{self.vid}:{self.pid}:{self.serial}"


class USBDiagnostics:
    """
    USB-диагностика для авторизованных устройств.

    Использование:
        usb = USBDiagnostics()
        devices = usb.scan_devices()
        usb.authorize_device("2341:0043", "Arduino Uno", DeviceType.ARDUINO_UNO)
        usb.connect("2341:0043")
        usb.send_command("AT")
    """

    def __init__(self, android_mode: bool = False):
        self.android_mode = android_mode
        self._authorized: Dict[str, AuthorizedDevice] = {}
        self._active_connections: Dict[str, Any] = {}
        self._read_callbacks: Dict[str, Callable] = {}
        self._load_authorized()

    def _load_authorized(self):
        """Загрузка списка авторизованных устройств."""
        os.makedirs("data", exist_ok=True)
        if os.path.exists(USB_DEVICES_FILE):
            try:
                with open(USB_DEVICES_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                for dev_data in data:
                    dev = AuthorizedDevice.from_dict(dev_data)
                    self._authorized[dev.device_id] = dev
                log.info("USB: загружено %d авторизованных устройств", len(self._authorized))
            except Exception as e:
                log.warning("USB: ошибка загрузки: %s", e)

    def _save_authorized(self):
        """Сохранение списка авторизованных устройств."""
        try:
            os.makedirs("data", exist_ok=True)
            with open(USB_DEVICES_FILE, "w", encoding="utf-8") as f:
                json.dump([d.to_dict() for d in self._authorized.values()], f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error("USB: ошибка сохранения: %s", e)

    @trace("usb.scan_devices")
    def scan_devices(self) -> List[Dict[str, Any]]:
        """
        Сканирование подключённых USB-устройств.

        Returns:
            Список обнаруженных устройств
        """
        devices = []

        if self.android_mode:
            devices = self._scan_android()
        else:
            devices = self._scan_desktop()

        log.info("USB: обнаружено %d устройств", len(devices))
        return devices

    def _scan_desktop(self) -> List[Dict[str, Any]]:
        """Сканирование на десктопе."""
        devices = []

        # Через pyserial
        try:
            import serial.tools.list_ports

            for port in serial.tools.list_ports.comports():
                dev_info = {
                    "port": port.device,
                    "vid": f"{port.vid:04X}" if port.vid else "0000",
                    "pid": f"{port.pid:04X}" if port.pid else "0000",
                    "serial": port.serial_number or "",
                    "description": port.description,
                    "manufacturer": port.manufacturer or "",
                    "product": port.product or "",
                    "device_type": self._detect_device_type(port.vid, port.pid),
                    "authorized": self._is_authorized(port.vid, port.pid, port.serial_number),
                }
                devices.append(dev_info)
        except ImportError:
            log.warning("USB: pyserial не установлен")
        except Exception as e:
            log.error("USB: ошибка сканирования: %s", e)

        return devices

    def _scan_android(self) -> List[Dict[str, Any]]:
        """Сканирование на Android через USB OTG."""
        devices = []

        try:
            from jnius import autoclass

            UsbManager = autoclass("android.hardware.usb.UsbManager")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            context = PythonActivity.mActivity

            usb_manager = context.getSystemService(context.USB_SERVICE)
            device_list = usb_manager.getDeviceList()

            for name in device_list.keySet():
                device = device_list.get(name)
                vid = f"{device.getVendorId():04X}"
                pid = f"{device.getProductId():04X}"
                serial = device.getSerialNumber() or ""

                dev_info = {
                    "port": name,
                    "vid": vid,
                    "pid": pid,
                    "serial": serial,
                    "description": device.getProductName() or "",
                    "manufacturer": device.getManufacturerName() or "",
                    "device_type": self._detect_device_type(device.getVendorId(), device.getProductId()),
                    "authorized": self._is_authorized(vid, pid, serial),
                }
                devices.append(dev_info)

        except Exception as e:
            log.debug("USB: Android API недоступен: %s", e)

        return devices

    def _detect_device_type(self, vid: int, pid: int) -> str:
        """Определение типа устройства по VID/PID."""
        # Известные VID/PID
        known_devices = {
            (0x2341, 0x0043): DeviceType.ARDUINO_UNO,
            (0x2341, 0x0001): DeviceType.ARDUINO_UNO,
            (0x2341, 0x0010): DeviceType.ARDUINO_MEGA,
            (0x2341, 0x0042): DeviceType.ARDUINO_MEGA,
            (0x1A86, 0x7523): DeviceType.ARDUINO_NANO,  # CH340
            (0x0403, 0x6001): DeviceType.GENERIC_SERIAL,  # FTDI
            (0x10C4, 0xEA60): DeviceType.ESP8266,  # CP2102
            (0x303A, 0x1001): DeviceType.ESP32,
            (0x303A, 0x80D1): DeviceType.ESP32,
            (0x2E8A, 0x0005): DeviceType.RP2040,
            (0x0483, 0x5740): DeviceType.STM32,
        }

        return known_devices.get((vid, pid), DeviceType.UNKNOWN).value

    def _is_authorized(self, vid: str, pid: str, serial: str) -> bool:
        """Проверка авторизации устройства."""
        device_id = f"{vid}:{pid}:{serial or ''}"
        return device_id in self._authorized

    @trace("usb.authorize_device")
    def authorize_device(
        self,
        vid_pid: str,
        name: str,
        device_type: DeviceType,
        serial: str = "",
        baudrate: int = 115200,
        notes: str = "",
    ) -> AuthorizedDevice:
        """
        Авторизация нового устройства.

        Args:
            vid_pid: VID:PID в формате "2341:0043"
            name: Человекочитаемое имя
            device_type: Тип устройства
            serial: Серийный номер (опционально)
            baudrate: Скорость подключения
            notes: Заметки

        Returns:
            Авторизованное устройство
        """
        vid, pid = vid_pid.split(":")

        device = AuthorizedDevice(
            vid=vid.upper(),
            pid=pid.upper(),
            serial=serial,
            name=name,
            device_type=device_type.value,
            baudrate=baudrate,
            authorized_at=time.time(),
            last_connected=0,
            notes=notes,
        )

        self._authorized[device.device_id] = device
        self._save_authorized()
        log.info("USB: авторизовано устройство '%s' (%s)", name, vid_pid)
        return device

    def revoke_device(self, device_id: str) -> bool:
        """Отзыв авторизации устройства."""
        if device_id in self._authorized:
            del self._authorized[device_id]
            self._save_authorized()
            log.info("USB: авторизация отозвана для %s", device_id)
            return True
        return False

    def list_authorized(self) -> List[AuthorizedDevice]:
        """Список авторизованных устройств."""
        return list(self._authorized.values())

    @trace("usb.connect")
    def connect(self, port_or_vid_pid: str, baudrate: int = None) -> Tuple[bool, str]:
        """
        Подключение к устройству.

        Args:
            port_or_vid_pid: Порт (/dev/ttyUSB0) или VID:PID (2341:0043)
            baudrate: Скорость (если не указана, берётся из авторизации)

        Returns:
            (успех, сообщение)
        """
        # Находим порт
        port = None
        device = None

        if ":" in port_or_vid_pid and not port_or_vid_pid.startswith("/"):
            # Это VID:PID, ищем порт
            vid, pid = port_or_vid_pid.split(":")[:2]
            for dev in self.scan_devices():
                if dev["vid"] == vid.upper() and dev["pid"] == pid.upper():
                    port = dev["port"]
                    device_id = f"{dev['vid']}:{dev['pid']}:{dev['serial']}"
                    device = self._authorized.get(device_id)
                    break
            if not port:
                return False, f"Устройство {port_or_vid_pid} не найдено"
        else:
            port = port_or_vid_pid

        # Проверяем авторизацию
        if device is None:
            for dev in self.scan_devices():
                if dev["port"] == port:
                    if not dev["authorized"]:
                        return False, f"Устройство на {port} не авторизовано"
                    device_id = f"{dev['vid']}:{dev['pid']}:{dev['serial']}"
                    device = self._authorized.get(device_id)
                    break

        if device is None:
            return False, "Устройство не найдено в списке авторизованных"

        # Определяем baudrate
        if baudrate is None:
            baudrate = device.baudrate

        # Подключаемся
        try:
            import serial

            conn = serial.Serial(port, baudrate, timeout=1)
            self._active_connections[port] = {"connection": conn, "device": device, "connected_at": time.time()}

            # Обновляем время подключения
            device.last_connected = time.time()
            self._save_authorized()

            log.info("USB: подключено к '%s' на %s @ %d", device.name, port, baudrate)
            return True, f"Подключено к {device.name}"

        except Exception as e:
            log.error("USB: ошибка подключения к %s: %s", port, e)
            return False, str(e)

    def disconnect(self, port: str) -> bool:
        """Отключение от устройства."""
        if port in self._active_connections:
            try:
                self._active_connections[port]["connection"].close()
            except Exception:
                pass
            del self._active_connections[port]
            log.info("USB: отключено от %s", port)
            return True
        return False

    def disconnect_all(self):
        """Отключение от всех устройств."""
        for port in list(self._active_connections.keys()):
            self.disconnect(port)

    @trace("usb.send_command")
    def send_command(
        self, port: str, command: str, wait_response: bool = True, timeout: float = 2.0
    ) -> Tuple[bool, str]:
        """
        Отправка команды на устройство.

        Args:
            port: Порт устройства
            command: Команда для отправки
            wait_response: Ждать ответ
            timeout: Таймаут ожидания

        Returns:
            (успех, ответ/ошибка)
        """
        if port not in self._active_connections:
            return False, "Нет активного подключения"

        conn = self._active_connections[port]["connection"]

        try:
            # Отправляем команду
            if not command.endswith("\n"):
                command += "\n"
            conn.write(command.encode())
            conn.flush()

            if not wait_response:
                return True, "Команда отправлена"

            # Ждём ответ
            conn.timeout = timeout
            response = ""
            start = time.time()

            while time.time() - start < timeout:
                line = conn.readline().decode(errors="ignore")
                if line:
                    response += line
                else:
                    break

            log.debug("USB: команда '%s' -> '%s'", command.strip(), response.strip())
            return True, response.strip()

        except Exception as e:
            log.error("USB: ошибка отправки команды: %s", e)
            return False, str(e)

    def read_continuous(self, port: str, callback: Callable[[str], None], stop_event: threading.Event = None):
        """
        Непрерывное чтение данных с устройства.

        Args:
            port: Порт устройства
            callback: Функция обработки данных
            stop_event: Событие для остановки
        """
        if port not in self._active_connections:
            log.error("USB: нет подключения к %s", port)
            return

        conn = self._active_connections[port]["connection"]

        def read_loop():
            while stop_event is None or not stop_event.is_set():
                try:
                    if conn.in_waiting:
                        data = conn.readline().decode(errors="ignore").strip()
                        if data:
                            callback(data)
                    time.sleep(0.01)
                except Exception as e:
                    log.error("USB: ошибка чтения: %s", e)
                    break

        thread = threading.Thread(target=read_loop, daemon=True)
        thread.start()
        log.info("USB: запущено непрерывное чтение с %s", port)

    @trace("usb.upload_firmware")
    def upload_firmware(self, port: str, firmware_path: str, device_type: DeviceType = None) -> Tuple[bool, str]:
        """
        Загрузка прошивки на устройство.

        Args:
            port: Порт устройства
            firmware_path: Путь к файлу прошивки (.hex, .bin)
            device_type: Тип устройства (для выбора загрузчика)

        Returns:
            (успех, сообщение)
        """
        if not os.path.exists(firmware_path):
            return False, f"Файл не найден: {firmware_path}"

        # Определяем тип устройства
        if device_type is None:
            for dev in self.scan_devices():
                if dev["port"] == port:
                    device_type = DeviceType(dev["device_type"])
                    break

        if device_type is None:
            return False, "Не удалось определить тип устройства"

        # Отключаемся если подключены
        self.disconnect(port)

        try:
            import subprocess

            # Выбираем инструмент прошивки
            if device_type in [DeviceType.ARDUINO_UNO, DeviceType.ARDUINO_NANO, DeviceType.ARDUINO_MEGA]:
                # avrdude для Arduino
                cmd = [
                    "avrdude",
                    "-c",
                    "arduino",
                    "-p",
                    "atmega328p",
                    "-P",
                    port,
                    "-b",
                    "115200",
                    "-U",
                    f"flash:w:{firmware_path}:i",
                ]
            elif device_type in [DeviceType.ESP8266, DeviceType.ESP32]:
                # esptool для ESP
                cmd = ["esptool.py", "--port", port, "write_flash", "0x0", firmware_path]
            elif device_type == DeviceType.STM32:
                # stm32flash для STM32
                cmd = ["stm32flash", "-w", firmware_path, "-v", "-g", "0x0", port]
            elif device_type == DeviceType.RP2040:
                return False, "RP2040: используйте drag-n-drop в UF2 режиме"
            else:
                return False, f"Неподдерживаемый тип устройства: {device_type}"

            log.info("USB: прошивка %s на %s...", firmware_path, port)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                log.info("USB: прошивка успешно загружена")
                return True, "Прошивка успешно загружена"
            else:
                log.error("USB: ошибка прошивки: %s", result.stderr)
                return False, result.stderr

        except FileNotFoundError as e:
            return False, f"Инструмент прошивки не найден: {e}"
        except subprocess.TimeoutExpired:
            return False, "Таймаут прошивки"
        except Exception as e:
            return False, str(e)

    def get_device_info(self, port: str) -> Optional[Dict[str, Any]]:
        """Получение информации о подключённом устройстве."""
        if port in self._active_connections:
            conn_info = self._active_connections[port]
            device = conn_info["device"]
            return {
                "name": device.name,
                "type": device.device_type,
                "port": port,
                "baudrate": device.baudrate,
                "connected_at": conn_info["connected_at"],
                "connected_duration": time.time() - conn_info["connected_at"],
            }
        return None

    def get_status(self) -> Dict[str, Any]:
        """Статус USB-диагностики."""
        return {
            "authorized_count": len(self._authorized),
            "active_connections": len(self._active_connections),
            "connected_ports": list(self._active_connections.keys()),
            "mode": "android" if self.android_mode else "desktop",
        }


# Глобальный экземпляр
_usb_diag: Optional[USBDiagnostics] = None


def get_usb_diagnostics(android_mode: bool = False) -> USBDiagnostics:
    """Получение глобального USB-диагноста."""
    global _usb_diag
    if _usb_diag is None:
        _usb_diag = USBDiagnostics(android_mode)
    return _usb_diag


# CLI для тестирования
if __name__ == "__main__":
    import sys

    usb = USBDiagnostics()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "scan":
            devices = usb.scan_devices()
            for d in devices:
                auth = "✓" if d["authorized"] else "✗"
                print(f"[{auth}] {d['port']}: {d['description']} " f"({d['vid']}:{d['pid']}) - {d['device_type']}")

        elif cmd == "list":
            for dev in usb.list_authorized():
                print(f"• {dev.name} ({dev.vid}:{dev.pid}) - {dev.device_type}")

        elif cmd == "status":
            print(usb.get_status())
    else:
        print("USB Diagnostics для Argos")
        print("Использование: python usb_diagnostics.py [scan|list|status]")
