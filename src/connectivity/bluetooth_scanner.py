"""
bluetooth_scanner.py — Bluetooth-сканер для инвентаризации IoT
  Обнаружение BLE/Classic устройств в радиусе действия.
  Инвентаризация, мониторинг RSSI, автоопределение типов устройств.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Callable
from enum import Enum


class DeviceType(Enum):
    """Типы Bluetooth устройств."""

    UNKNOWN = "unknown"
    SMARTPHONE = "smartphone"
    COMPUTER = "computer"
    HEADPHONES = "headphones"
    SPEAKER = "speaker"
    SMARTWATCH = "smartwatch"
    FITNESS_TRACKER = "fitness_tracker"
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    GAMEPAD = "gamepad"
    IOT_SENSOR = "iot_sensor"
    SMART_HOME = "smart_home"
    BEACON = "beacon"
    MEDICAL = "medical"
    VEHICLE = "vehicle"


@dataclass
class BluetoothDevice:
    """Обнаруженное Bluetooth устройство."""

    address: str
    name: Optional[str] = None
    rssi: int = -100
    device_type: DeviceType = DeviceType.UNKNOWN
    is_ble: bool = False
    manufacturer: Optional[str] = None
    services: List[str] = field(default_factory=list)
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    seen_count: int = 1
    is_connectable: bool = False
    tx_power: Optional[int] = None
    extra_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Сериализация в словарь."""
        data = asdict(self)
        data["device_type"] = self.device_type.value
        return data

    def estimated_distance(self) -> Optional[float]:
        """Оценка расстояния по RSSI (в метрах)."""
        if self.tx_power is None:
            tx_power = -59  # Типичное значение для BLE
        else:
            tx_power = self.tx_power

        if self.rssi == 0:
            return None

        # Формула расчёта расстояния по RSSI
        ratio = self.rssi / tx_power
        if ratio < 1.0:
            return ratio**10
        else:
            return 0.89976 * (ratio**7.7095) + 0.111


class ArgosBluetoothScanner:
    """
    Bluetooth-сканер Аргоса для инвентаризации IoT.

    Возможности:
    - Сканирование BLE и Classic Bluetooth
    - Автоопределение типа устройства
    - Мониторинг RSSI (сила сигнала)
    - Ведение инвентаря устройств
    - Оценка расстояния до устройств
    - Уведомления о новых устройствах
    """

    # Известные префиксы MAC для определения производителя
    MAC_PREFIXES = {
        "00:1A:7D": "Apple",
        "F4:F5:D8": "Apple",
        "A4:83:E7": "Apple",
        "00:25:00": "Apple",
        "88:E9:FE": "Apple",
        "AC:BC:32": "Apple",
        "00:1E:C0": "Samsung",
        "84:38:35": "Samsung",
        "C4:57:6E": "Samsung",
        "00:26:E8": "Xiaomi",
        "64:CC:2E": "Xiaomi",
        "28:6C:07": "Xiaomi",
        "00:1A:11": "Google",
        "F8:8F:CA": "Google",
        "00:09:2D": "ESP32",
        "24:6F:28": "ESP32",
        "30:AE:A4": "ESP32",
        "A4:CF:12": "ESP8266",
        "18:FE:34": "ESP8266",
        "5C:CF:7F": "ESP8266",
        "B4:E6:2D": "Raspberry Pi",
        "DC:A6:32": "Raspberry Pi",
        "E4:5F:01": "Raspberry Pi",
    }

    # Профили Bluetooth для определения типа устройства
    SERVICE_PROFILES = {
        "0000110b": DeviceType.SPEAKER,  # A2DP Sink
        "0000110a": DeviceType.HEADPHONES,  # A2DP Source
        "00001108": DeviceType.HEADPHONES,  # Headset
        "0000111e": DeviceType.SMARTPHONE,  # Handsfree
        "00001124": DeviceType.KEYBOARD,  # HID
        "0000180d": DeviceType.FITNESS_TRACKER,  # Heart Rate
        "0000180f": DeviceType.IOT_SENSOR,  # Battery Service
        "00001809": DeviceType.MEDICAL,  # Health Thermometer
        "0000181a": DeviceType.IOT_SENSOR,  # Environmental Sensing
        "0000feaa": DeviceType.BEACON,  # Eddystone
    }

    def __init__(self, inventory_path: str = "data/bluetooth_inventory.json"):
        """
        Инициализация сканера.

        Args:
            inventory_path: Путь к файлу инвентаря устройств
        """
        self.inventory_path = inventory_path
        self.devices: Dict[str, BluetoothDevice] = {}
        self.scan_running = False
        self.on_new_device: Optional[Callable[[BluetoothDevice], None]] = None
        self.on_device_lost: Optional[Callable[[BluetoothDevice], None]] = None
        self._scanner = None
        self._platform = self._detect_platform()

        self._load_inventory()

    def _detect_platform(self) -> str:
        """Определение платформы."""
        try:
            from jnius import autoclass

            return "android"
        except ImportError:
            pass

        try:
            import bleak

            return "bleak"
        except ImportError:
            pass

        return "mock"

    def _load_inventory(self):
        """Загрузка сохранённого инвентаря."""
        if os.path.exists(self.inventory_path):
            try:
                with open(self.inventory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for addr, dev_data in data.items():
                    dev_data["device_type"] = DeviceType(dev_data.get("device_type", "unknown"))
                    self.devices[addr] = BluetoothDevice(**dev_data)

                print(f"[BT SCANNER]: Загружено {len(self.devices)} устройств из инвентаря")
            except Exception as e:
                print(f"[BT SCANNER]: Ошибка загрузки инвентаря: {e}")

    def _save_inventory(self):
        """Сохранение инвентаря."""
        try:
            os.makedirs(os.path.dirname(self.inventory_path), exist_ok=True)

            data = {addr: dev.to_dict() for addr, dev in self.devices.items()}

            with open(self.inventory_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[BT SCANNER]: Ошибка сохранения инвентаря: {e}")

    def _identify_manufacturer(self, address: str) -> Optional[str]:
        """Определение производителя по MAC-адресу."""
        prefix = address[:8].upper()
        return self.MAC_PREFIXES.get(prefix)

    def _identify_device_type(self, name: Optional[str], services: List[str]) -> DeviceType:
        """Определение типа устройства."""
        # По сервисам
        for service in services:
            service_short = service.replace("-", "")[:8].lower()
            if service_short in self.SERVICE_PROFILES:
                return self.SERVICE_PROFILES[service_short]

        # По имени
        if name:
            name_lower = name.lower()

            if any(kw in name_lower for kw in ["phone", "iphone", "galaxy", "pixel", "xiaomi", "huawei"]):
                return DeviceType.SMARTPHONE
            if any(kw in name_lower for kw in ["macbook", "laptop", "pc", "computer", "desktop"]):
                return DeviceType.COMPUTER
            if any(kw in name_lower for kw in ["airpod", "buds", "headphone", "earphone", "earbuds"]):
                return DeviceType.HEADPHONES
            if any(kw in name_lower for kw in ["speaker", "soundbar", "jbl", "bose", "sonos"]):
                return DeviceType.SPEAKER
            if any(kw in name_lower for kw in ["watch", "band", "mi band", "fitbit", "garmin"]):
                return DeviceType.SMARTWATCH
            if any(kw in name_lower for kw in ["keyboard", "keychron", "logitech k"]):
                return DeviceType.KEYBOARD
            if any(kw in name_lower for kw in ["mouse", "mx master", "trackpad"]):
                return DeviceType.MOUSE
            if any(kw in name_lower for kw in ["gamepad", "controller", "xbox", "playstation", "dualshock"]):
                return DeviceType.GAMEPAD
            if any(kw in name_lower for kw in ["esp", "arduino", "sensor", "temp", "humidity"]):
                return DeviceType.IOT_SENSOR
            if any(kw in name_lower for kw in ["bulb", "light", "plug", "switch", "yeelight", "smartlife"]):
                return DeviceType.SMART_HOME
            if any(kw in name_lower for kw in ["beacon", "tile", "airtag", "smarttag"]):
                return DeviceType.BEACON

        return DeviceType.UNKNOWN

    def _process_device(
        self,
        address: str,
        name: Optional[str],
        rssi: int,
        is_ble: bool = True,
        services: List[str] = None,
        tx_power: Optional[int] = None,
        extra_data: Dict = None,
    ):
        """Обработка обнаруженного устройства."""
        services = services or []
        extra_data = extra_data or {}

        is_new = address not in self.devices

        if is_new:
            device = BluetoothDevice(
                address=address,
                name=name,
                rssi=rssi,
                is_ble=is_ble,
                manufacturer=self._identify_manufacturer(address),
                services=services,
                device_type=self._identify_device_type(name, services),
                tx_power=tx_power,
                extra_data=extra_data,
                is_connectable=True,
            )
            self.devices[address] = device

            print(f"[BT SCANNER]: Новое устройство: {name or address} ({device.device_type.value})")

            if self.on_new_device:
                self.on_new_device(device)
        else:
            device = self.devices[address]
            device.rssi = rssi
            device.last_seen = datetime.now().isoformat()
            device.seen_count += 1

            if name and not device.name:
                device.name = name

            if services and not device.services:
                device.services = services
                device.device_type = self._identify_device_type(name, services)

            if tx_power is not None:
                device.tx_power = tx_power

    async def scan_ble(self, duration: float = 10.0) -> List[BluetoothDevice]:
        """
        Сканирование BLE устройств (используя bleak).

        Args:
            duration: Длительность сканирования в секундах

        Returns:
            Список обнаруженных устройств
        """
        if self._platform == "bleak":
            try:
                from bleak import BleakScanner

                print(f"[BT SCANNER]: BLE сканирование {duration}с...")

                devices = await BleakScanner.discover(timeout=duration)

                for d in devices:
                    self._process_device(
                        address=d.address, name=d.name, rssi=d.rssi if hasattr(d, "rssi") else -100, is_ble=True
                    )

                self._save_inventory()
                return list(self.devices.values())

            except Exception as e:
                print(f"[BT SCANNER]: Ошибка BLE: {e}")
                return []

        elif self._platform == "android":
            return await self._scan_android_ble(duration)

        else:
            print("[BT SCANNER]: Bluetooth недоступен (mock режим)")
            return list(self.devices.values())

    async def _scan_android_ble(self, duration: float) -> List[BluetoothDevice]:
        """Сканирование BLE на Android."""
        try:
            from jnius import autoclass

            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            BluetoothDevice = autoclass("android.bluetooth.BluetoothDevice")

            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None:
                print("[BT SCANNER]: Bluetooth адаптер недоступен")
                return []

            if not adapter.isEnabled():
                print("[BT SCANNER]: Bluetooth выключен")
                return []

            # BLE сканирование через Android API
            scanner = adapter.getBluetoothLeScanner()
            if scanner is None:
                print("[BT SCANNER]: BLE сканер недоступен")
                return []

            # Запуск сканирования
            print(f"[BT SCANNER]: Android BLE сканирование {duration}с...")

            # Получение bonded (сопряжённых) устройств
            bonded = adapter.getBondedDevices().toArray()
            for device in bonded:
                self._process_device(
                    address=device.getAddress(),
                    name=device.getName(),
                    rssi=-50,  # Сопряжённые обычно близко
                    is_ble=False,
                )

            await asyncio.sleep(duration)
            self._save_inventory()

            return list(self.devices.values())

        except Exception as e:
            print(f"[BT SCANNER]: Ошибка Android BLE: {e}")
            return []

    def scan_sync(self, duration: float = 10.0) -> List[BluetoothDevice]:
        """Синхронная обёртка для сканирования."""
        return asyncio.get_event_loop().run_until_complete(self.scan_ble(duration))

    def get_inventory(self) -> List[Dict]:
        """Получение полного инвентаря устройств."""
        return [dev.to_dict() for dev in self.devices.values()]

    def get_device(self, address: str) -> Optional[BluetoothDevice]:
        """Получение устройства по адресу."""
        return self.devices.get(address.upper())

    def get_devices_by_type(self, device_type: DeviceType) -> List[BluetoothDevice]:
        """Фильтрация устройств по типу."""
        return [d for d in self.devices.values() if d.device_type == device_type]

    def get_nearby_devices(self, rssi_threshold: int = -70) -> List[BluetoothDevice]:
        """Получение ближайших устройств по RSSI."""
        return [d for d in self.devices.values() if d.rssi >= rssi_threshold]

    def get_iot_devices(self) -> List[BluetoothDevice]:
        """Получение IoT устройств."""
        iot_types = {DeviceType.IOT_SENSOR, DeviceType.SMART_HOME, DeviceType.BEACON}
        return [d for d in self.devices.values() if d.device_type in iot_types]

    def forget_device(self, address: str) -> bool:
        """Удаление устройства из инвентаря."""
        if address in self.devices:
            del self.devices[address]
            self._save_inventory()
            return True
        return False

    def clear_inventory(self):
        """Очистка всего инвентаря."""
        self.devices.clear()
        self._save_inventory()

    def get_statistics(self) -> Dict:
        """Статистика по обнаруженным устройствам."""
        type_counts = {}
        for dev in self.devices.values():
            type_name = dev.device_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        manufacturers = {}
        for dev in self.devices.values():
            mfr = dev.manufacturer or "Unknown"
            manufacturers[mfr] = manufacturers.get(mfr, 0) + 1

        return {
            "total_devices": len(self.devices),
            "by_type": type_counts,
            "by_manufacturer": manufacturers,
            "ble_devices": sum(1 for d in self.devices.values() if d.is_ble),
            "classic_devices": sum(1 for d in self.devices.values() if not d.is_ble),
            "iot_devices": len(self.get_iot_devices()),
            "nearby_devices": len(self.get_nearby_devices()),
        }

    def print_inventory(self):
        """Вывод инвентаря в консоль."""
        print("\n" + "=" * 60)
        print("📡 BLUETOOTH ИНВЕНТАРЬ АРГОСА")
        print("=" * 60)

        if not self.devices:
            print("  Устройства не обнаружены")
            return

        # Сортировка по RSSI (ближайшие первыми)
        sorted_devices = sorted(self.devices.values(), key=lambda d: d.rssi, reverse=True)

        for dev in sorted_devices:
            icon = self._get_device_icon(dev.device_type)
            name = dev.name or dev.address
            distance = dev.estimated_distance()
            dist_str = f"~{distance:.1f}м" if distance else "?"

            print(f"\n  {icon} {name}")
            print(f"     MAC: {dev.address}")
            print(f"     RSSI: {dev.rssi} dBm | Расстояние: {dist_str}")
            print(f"     Тип: {dev.device_type.value} | {'BLE' if dev.is_ble else 'Classic'}")
            if dev.manufacturer:
                print(f"     Производитель: {dev.manufacturer}")
            print(f"     Видели: {dev.seen_count}x | Последний раз: {dev.last_seen[:19]}")

        print("\n" + "=" * 60)
        stats = self.get_statistics()
        print(f"Всего: {stats['total_devices']} | IoT: {stats['iot_devices']} | Рядом: {stats['nearby_devices']}")
        print("=" * 60 + "\n")

    def _get_device_icon(self, device_type: DeviceType) -> str:
        """Иконка для типа устройства."""
        icons = {
            DeviceType.SMARTPHONE: "📱",
            DeviceType.COMPUTER: "💻",
            DeviceType.HEADPHONES: "🎧",
            DeviceType.SPEAKER: "🔊",
            DeviceType.SMARTWATCH: "⌚",
            DeviceType.FITNESS_TRACKER: "💪",
            DeviceType.KEYBOARD: "⌨️",
            DeviceType.MOUSE: "🖱️",
            DeviceType.GAMEPAD: "🎮",
            DeviceType.IOT_SENSOR: "📡",
            DeviceType.SMART_HOME: "🏠",
            DeviceType.BEACON: "📍",
            DeviceType.MEDICAL: "🏥",
            DeviceType.VEHICLE: "🚗",
            DeviceType.UNKNOWN: "❓",
        }
        return icons.get(device_type, "❓")


# CLI интерфейс
if __name__ == "__main__":
    import sys

    scanner = ArgosBluetoothScanner()

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()

        if cmd == "scan":
            duration = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
            asyncio.run(scanner.scan_ble(duration))
            scanner.print_inventory()

        elif cmd == "list":
            scanner.print_inventory()

        elif cmd == "stats":
            import json

            print(json.dumps(scanner.get_statistics(), indent=2, ensure_ascii=False))

        elif cmd == "iot":
            iot = scanner.get_iot_devices()
            print(f"\n📡 IoT устройства ({len(iot)}):")
            for dev in iot:
                print(f"  - {dev.name or dev.address}: {dev.device_type.value}")

        elif cmd == "clear":
            scanner.clear_inventory()
            print("Инвентарь очищен")

        else:
            print("Использование: bluetooth_scanner.py [scan|list|stats|iot|clear] [duration]")
    else:
        # Сканирование по умолчанию
        asyncio.run(scanner.scan_ble(10.0))
        scanner.print_inventory()


# README alias
BluetoothScanner = ArgosBluetoothScanner
