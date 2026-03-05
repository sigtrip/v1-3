"""
iot_bridge.py — IoT-мост Аргоса
  Поддержка: Zigbee (zigpy/zigbee2mqtt), LoRa (pyserial + AT),
             Mesh (ESP-NOW / custom UDP mesh), MQTT, Modbus (RTU/ASCII/TCP),
             BACnet, KNX, LonWorks, M-Bus, OPC UA.
  Аргос — оператор умных систем: дом, теплица, гараж, погреб,
  инкубатор, аквариум, террариум.
"""

import importlib.util
import json
import logging
import os
import socket
import sqlite3
import struct
import threading
import time
from collections import defaultdict

from src.argos_logger import get_logger
from src.event_bus import Events, get_bus
from src.observability import log_iot, trace

log = get_logger("argos.iot")
modbus_log = logging.getLogger("argos.iot_bridge")
bus = get_bus()

try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient

    MODBUS_OK = True
except ImportError:
    MODBUS_OK = False

SUPPORTED_ZIGBEE_HUBS = [
    "Aqara Hub M2",
    "Aqara Hub M1S Gen 2",
    "Xiaomi Mi Smart Home Hub (Multi-mode)",
    "Xiaomi Smart Home Hub 2",
    "Яндекс Станция Миди (со встроенным хабом)",
    "Яндекс Станция 2 (со встроенным хабом)",
    "Яндекс Станция Макс (с Zigbee)",
    "Tuya / Moes Multi-mode Gateway",
    "Digma Smart Zigbee Gateway",
    "Hubitat Elevation C-8",
]

SUPPORTED_ZIGBEE_COORDINATORS = [
    "Sonoff Zigbee 3.0 USB Dongle Plus (ZBDongle-P)",
    "Sonoff Zigbee 3.0 USB Dongle Plus (ZBDongle-E)",
    "SMLIGHT SLZB-06 / 06M (Ethernet/PoE/USB)",
    "Home Assistant SkyConnect",
    "ConBee II / ConBee III",
    "ZigStar Stick v4",
    "JetHome USB Zigbee Stick",
    "Aeotec Zi-Stick",
    "Ugreen Zigbee USB Adapter",
    "CC2531 (устаревшая бюджетная модель)",
]

# Реестр всех устройств
DEVICES_FILE = "data/iot_devices.json"
IOT_DB_PATH = "data/argos.db"


class IoTDevice:
    def __init__(self, device_id: str, dtype: str, protocol: str, address: str = "", name: str = ""):
        self.id = device_id
        self.type = dtype  # sensor | actuator | gateway
        self.protocol = protocol  # zigbee | lora | mesh | mqtt | modbus
        self.address = address
        self.name = name or device_id
        self.state: dict = {}
        self.last_seen: float = 0
        self.online: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "protocol": self.protocol,
            "address": self.address,
            "name": self.name,
            "state": self.state,
            "last_seen": self.last_seen,
            "online": self.online,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IoTDevice":
        dev = cls(d["id"], d["type"], d["protocol"], d.get("address", ""), d.get("name", ""))
        dev.state = d.get("state", {})
        dev.last_seen = d.get("last_seen", 0)
        dev.online = d.get("online", False)
        return dev

    def update(self, key: str, value):
        old = self.state.get(key)
        self.state[key] = value
        self.last_seen = time.time()
        self.online = True
        log_iot(self.id, key, value)
        if old != value:
            bus.emit(Events.IOT_VALUE_CHANGED, {"device": self.id, "key": key, "old": old, "new": value}, "iot_bridge")


class IoTRegistry:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self._devices: dict[str, IoTDevice] = {}
        self._load()

    def _load(self):
        if os.path.exists(DEVICES_FILE):
            try:
                data = json.load(open(DEVICES_FILE, encoding="utf-8"))
                for d in data:
                    dev = IoTDevice.from_dict(d)
                    self._devices[dev.id] = dev
                log.info("IoT: загружено %d устройств", len(self._devices))
            except Exception as e:
                log.warning("IoT registry load error: %s", e)

    def save(self):
        try:
            data = [d.to_dict() for d in self._devices.values()]
            json.dump(data, open(DEVICES_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        except Exception as e:
            log.error("IoT save error: %s", e)

    def register(self, dev: IoTDevice) -> str:
        self._devices[dev.id] = dev
        self.save()
        bus.emit(Events.IOT_DEVICE_FOUND, dev.to_dict(), "iot_registry")
        log.info("IoT: зарегистрировано %s [%s/%s]", dev.name, dev.protocol, dev.type)
        return f"✅ Устройство '{dev.name}' зарегистрировано."

    def get(self, dev_id: str) -> IoTDevice | None:
        return self._devices.get(dev_id)

    def all(self) -> list[IoTDevice]:
        return list(self._devices.values())

    def online(self) -> list[IoTDevice]:
        return [d for d in self._devices.values() if d.online]

    def report(self) -> str:
        devices = self.all()
        if not devices:
            return "📡 IoT устройств нет. Подключи через: зарегистрируй устройство"
        lines = [f"📡 IoT СЕТЬ ({len(devices)} устройств):"]
        by_proto = defaultdict(list)
        for d in devices:
            by_proto[d.protocol].append(d)
        for proto, devs in sorted(by_proto.items()):
            lines.append(f"\n  [{proto.upper()}]")
            for d in devs:
                status = "🟢" if d.online else "🔴"
                ago = _ago(d.last_seen)
                state = ", ".join(f"{k}={v}" for k, v in list(d.state.items())[:3])
                lines.append(f"    {status} {d.name} [{d.type}] {ago}")
                if state:
                    lines.append(f"       {state}")
        return "\n".join(lines)


def _ago(ts: float) -> str:
    if not ts:
        return "никогда"
    s = int(time.time() - ts)
    if s < 60:
        return f"{s}с назад"
    if s < 3600:
        return f"{s//60}м назад"
    return f"{s//3600}ч назад"


# ══════════════════════════════════════════════════════════
# ПРОТОКОЛЫ
# ══════════════════════════════════════════════════════════


class ZigbeeAdapter:
    """Адаптер Zigbee через zigbee2mqtt (MQTT) или zigpy."""

    def __init__(self, registry: IoTRegistry):
        self.registry = registry
        self._mqtt = None

    def connect_mqtt(self, host: str = "localhost", port: int = 1883, topic: str = "zigbee2mqtt/#") -> str:
        try:
            import paho.mqtt.client as mqtt

            client = mqtt.Client()
            client.on_message = self._on_mqtt_message
            client.connect(host, port, 60)
            client.subscribe(topic)
            client.loop_start()
            self._mqtt = client
            log.info("Zigbee MQTT подключён: %s:%d", host, port)
            return f"✅ Zigbee MQTT: {host}:{port} тема {topic}"
        except ImportError:
            return "❌ pip install paho-mqtt"
        except Exception as e:
            return f"❌ Zigbee MQTT: {e}"

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            topic = msg.topic.replace("zigbee2mqtt/", "")
            data = json.loads(msg.payload.decode())
            dev_id = f"zb_{topic.replace('/','_')}"
            dev = self.registry.get(dev_id)
            if not dev:
                dev = IoTDevice(dev_id, "sensor", "zigbee", topic, topic)
                self.registry.register(dev)
            for k, v in data.items():
                dev.update(k, v)
        except Exception as e:
            log.error("Zigbee MQTT parse: %s", e)

    def send_command(self, device_name: str, payload: dict) -> str:
        if not self._mqtt:
            return "❌ MQTT не подключён."
        try:
            topic = f"zigbee2mqtt/{device_name}/set"
            self._mqtt.publish(topic, json.dumps(payload))
            return f"✅ Команда отправлена: {device_name} ← {payload}"
        except Exception as e:
            return f"❌ {e}"


class LoRaAdapter:
    """Адаптер LoRa через UART (AT-команды) или pyserial."""

    def __init__(self, registry: IoTRegistry):
        self.registry = registry
        self._serial = None
        self._port = None
        self._running = False

    def connect(self, port: str = "/dev/ttyUSB0", baud: int = 9600, freq: float = 433.0) -> str:
        try:
            import serial

            self._serial = serial.Serial(port, baud, timeout=2)
            self._port = port
            # Инициализация LoRa модема AT-командами
            self._serial.write(b"AT+RESET\r\n")
            time.sleep(1)
            self._serial.write(f"AT+FREQ={freq}\r\n".encode())
            time.sleep(0.5)
            self._serial.write(b"AT+MODE=0\r\n")  # normal mode
            self._running = True
            threading.Thread(target=self._read_loop, daemon=True).start()
            log.info("LoRa подключён: %s, %.1fMHz", port, freq)
            return f"✅ LoRa: {port} @ {freq}MHz"
        except ImportError:
            return "❌ pip install pyserial"
        except Exception as e:
            return f"❌ LoRa: {e}"

    def _read_loop(self):
        while self._running and self._serial:
            try:
                line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("+RCV="):
                    # +RCV=addr,len,data,rssi,snr
                    parts = line[5:].split(",")
                    if len(parts) >= 3:
                        addr = parts[0]
                        data = parts[2]
                        self._parse_lora_packet(addr, data)
            except Exception as e:
                if self._running:
                    log.error("LoRa read: %s", e)

    def _parse_lora_packet(self, addr: str, data: str):
        dev_id = f"lora_{addr}"
        dev = self.registry.get(dev_id)
        if not dev:
            dev = IoTDevice(dev_id, "sensor", "lora", addr, f"LoRa-{addr}")
            self.registry.register(dev)
        # Формат: key:value,key:value
        for pair in data.split(","):
            if ":" in pair:
                k, v = pair.split(":", 1)
                try:
                    v = float(v)
                except ValueError:
                    pass
                dev.update(k.strip(), v)
        log.debug("LoRa пакет от %s: %s", addr, data[:50])

    def send(self, addr: str, data: str) -> str:
        if not self._serial:
            return "❌ LoRa не подключён."
        try:
            cmd = f"AT+SEND={addr},{len(data)},{data}\r\n"
            self._serial.write(cmd.encode())
            time.sleep(0.3)
            return f"✅ LoRa → {addr}: {data[:50]}"
        except Exception as e:
            return f"❌ {e}"

    def broadcast(self, data: str) -> str:
        return self.send("255", data)  # broadcast addr


class MeshAdapter:
    """UDP Mesh сеть (ESP-NOW совместимый протокол через Wi-Fi)."""

    def __init__(self, registry: IoTRegistry, port: int = 9876):
        self.registry = registry
        self.port = port
        self._sock = None
        self._running = False

    def start(self) -> str:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._sock.bind(("", self.port))
            self._running = True
            threading.Thread(target=self._listen, daemon=True).start()
            log.info("Mesh UDP запущен на порту %d", self.port)
            return f"✅ Mesh UDP слушает порт {self.port}"
        except Exception as e:
            return f"❌ Mesh: {e}"

    def _listen(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(4096)
                self._parse_packet(data, addr[0])
            except Exception as e:
                if self._running:
                    log.error("Mesh recv: %s", e)

    def _parse_packet(self, raw: bytes, ip: str):
        try:
            pkt = json.loads(raw.decode())
            dev_id = f"mesh_{pkt.get('id', ip.replace('.','_'))}"
            dev = self.registry.get(dev_id)
            if not dev:
                dev = IoTDevice(dev_id, pkt.get("type", "sensor"), "mesh", ip, pkt.get("name", dev_id))
                self.registry.register(dev)
            for k, v in pkt.get("data", {}).items():
                dev.update(k, v)
        except Exception as e:
            log.error("Mesh parse: %s", e)

    def send(self, ip: str, payload: dict) -> str:
        if not self._sock:
            return "❌ Mesh не запущен."
        try:
            data = json.dumps(payload).encode()
            self._sock.sendto(data, (ip, self.port))
            return f"✅ Mesh → {ip}: {payload}"
        except Exception as e:
            return f"❌ {e}"

    def broadcast(self, payload: dict) -> str:
        return self.send("255.255.255.255", payload)


class MQTTBroker:
    """Обёртка над paho-mqtt для общего MQTT брокера."""

    def __init__(self, registry: IoTRegistry):
        self.registry = registry
        self._client = None
        self._callbacks = {}

    def connect(self, host: str = "localhost", port: int = 1883) -> str:
        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client()
            self._client.on_message = self._on_message
            self._client.on_connect = lambda c, u, f, rc: log.info("MQTT connected rc=%d", rc)
            self._client.connect(host, port, 60)
            self._client.loop_start()
            return f"✅ MQTT брокер: {host}:{port}"
        except ImportError:
            return "❌ pip install paho-mqtt"
        except Exception as e:
            return f"❌ MQTT: {e}"

    def subscribe(self, topic: str, callback=None) -> str:
        if not self._client:
            return "MQTT не подключён."
        self._client.subscribe(topic)
        if callback:
            self._callbacks[topic] = callback
        return f"✅ Подписан на: {topic}"

    def publish(self, topic: str, payload: dict | str) -> str:
        if not self._client:
            return "MQTT не подключён."
        msg = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        self._client.publish(topic, msg)
        return f"✅ MQTT → {topic}: {msg[:50]}"

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        cb = self._callbacks.get(topic)
        if cb:
            try:
                cb(msg.topic, msg.payload)
            except Exception as e:
                log.error("MQTT cb: %s", e)


class ModbusAdapter:
    """Минимальный runtime-адаптер Modbus (RTU/TCP) через pymodbus."""

    def __init__(self, registry: IoTRegistry):
        self.registry = registry
        self._client = None
        self._mode = None
        self._endpoint = None

    def connect_serial(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        parity: str = "N",
        stopbits: int = 1,
        bytesize: int = 8,
        timeout: float = 2.0,
    ) -> str:
        if not MODBUS_OK:
            return "❌ Modbus: установи pip install pymodbus"

        try:
            client = ModbusSerialClient(
                method="rtu",
                port=port,
                baudrate=baudrate,
                parity=parity,
                stopbits=stopbits,
                bytesize=bytesize,
                timeout=timeout,
            )
            if not client.connect():
                return f"❌ Modbus RTU: не удалось подключиться к {port}"
            self._client = client
            self._mode = "rtu"
            self._endpoint = f"{port}:{baudrate}"
            modbus_log.info("Modbus RTU подключен: %s at %d baud", port, baudrate)
            return f"✅ Modbus RTU успешно запущен на {port} ({baudrate} бод)."
        except Exception as e:
            modbus_log.error("Modbus RTU error: %s", e)
            return f"❌ Ошибка Modbus RTU: {e}"

    def connect_rtu(self, port: str, baudrate: int) -> str:
        """Совместимость с командами core: подключи modbus [port] [baud]."""
        return self.connect_serial(port=port, baudrate=baudrate)

    def connect_tcp(self, host: str = "127.0.0.1", port: int = 502, timeout: float = 2.0) -> str:
        if not MODBUS_OK:
            return "❌ Modbus: установи pip install pymodbus"

        try:
            client = ModbusTcpClient(host=host, port=port, timeout=timeout)
            if not client.connect():
                return f"❌ Modbus TCP: не удалось подключиться к {host}:{port}"
            self._client = client
            self._mode = "tcp"
            self._endpoint = f"{host}:{port}"
            modbus_log.info("Modbus TCP подключен: %s:%d", host, port)
            return f"✅ Modbus TCP успешно подключен к {host}:{port}."
        except Exception as e:
            modbus_log.error("Modbus TCP error: %s", e)
            return f"❌ Ошибка Modbus TCP: {e}"

    def _ensure_device(self, unit: int) -> IoTDevice:
        dev_id = f"modbus_u{unit}"
        dev = self.registry.get(dev_id)
        if not dev:
            dev = IoTDevice(dev_id, "sensor", "modbus", self._endpoint or "modbus", f"Modbus Unit {unit}")
            self.registry.register(dev)
        return dev

    def read_holding(self, address: int, count: int = 1, unit: int = 1) -> str:
        if not self._client:
            return "❌ Modbus не подключён. Сначала: подключи modbus ..."
        try:
            try:
                rr = self._client.read_holding_registers(address=address, count=count, slave=unit)
            except TypeError:
                rr = self._client.read_holding_registers(address=address, count=count, unit=unit)

            if rr is None:
                return "❌ Modbus: пустой ответ"
            if hasattr(rr, "isError") and rr.isError():
                return f"❌ Modbus read error: {rr}"

            regs = list(getattr(rr, "registers", []) or [])
            dev = self._ensure_device(unit)
            for idx, val in enumerate(regs):
                dev.update(f"hr_{address + idx}", val)
            return f"✅ Modbus U{unit} HR[{address}:{address + max(0, count - 1)}] = {regs}"
        except Exception as e:
            return f"❌ Modbus read: {e}"

    def write_register(self, address: int, value: int, unit: int = 1) -> str:
        if not self._client:
            return "❌ Modbus не подключён. Сначала: подключи modbus ..."
        try:
            try:
                wr = self._client.write_register(address=address, value=value, slave=unit)
            except TypeError:
                wr = self._client.write_register(address=address, value=value, unit=unit)

            if wr is None:
                return "❌ Modbus: пустой ответ"
            if hasattr(wr, "isError") and wr.isError():
                return f"❌ Modbus write error: {wr}"

            dev = self._ensure_device(unit)
            dev.update(f"hr_{address}", value)
            return f"📤 Modbus (Slave {unit}): В регистр {address} успешно записано значение {value}."
        except Exception as e:
            return f"❌ Modbus write: {e}"

    def write_holding(self, address: int, value: int, slave: int) -> str:
        """Совместимость с требуемым API: write_holding(address, value, slave)."""
        return self.write_register(address=address, value=value, unit=slave)

    def status(self) -> str:
        if not self._client:
            return "🔴 Modbus: не подключён"
        return f"🟢 Modbus: {self._mode or 'unknown'} {self._endpoint or ''}".strip()


class TasmotaDiscoveryBridge:
    """Zero-config мост для Tasmota discovery через Home Assistant MQTT топики."""

    def __init__(self, registry: IoTRegistry, db_path: str = IOT_DB_PATH):
        self.registry = registry
        self.db_path = db_path
        self._client = None
        self._connected = False
        self._lock = threading.Lock()
        self._discovered_components: dict[str, set[str]] = defaultdict(set)
        self._ensure_db()

    def _ensure_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path) or "data", exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS iot_devices (
                    device_id    TEXT PRIMARY KEY,
                    name         TEXT,
                    protocol     TEXT,
                    dtype        TEXT,
                    address      TEXT,
                    source_topic TEXT,
                    component    TEXT,
                    payload_json TEXT,
                    first_seen   REAL,
                    last_seen    REAL
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning("TasmotaDiscovery DB init error: %s", e)

    def connect(self, host: str = "localhost", port: int = 1883, topic: str = "homeassistant/#") -> str:
        try:
            import paho.mqtt.client as mqtt

            self._client = mqtt.Client()
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.connect(host, port, 60)
            self._client.subscribe(topic)
            self._client.loop_start()
            self._connected = True
            log.info("Tasmota Discovery bridge: %s:%d %s", host, port, topic)
            return f"✅ Tasmota Discovery MQTT: {host}:{port} тема {topic}"
        except ImportError:
            return "❌ pip install paho-mqtt"
        except Exception as e:
            self._connected = False
            return f"❌ Tasmota Discovery: {e}"

    def _on_connect(self, client, userdata, flags, rc):
        log.info("Tasmota Discovery MQTT connected rc=%s", rc)

    def _on_message(self, client, userdata, msg):
        topic = str(msg.topic or "")
        if not topic.startswith("homeassistant/") or not topic.endswith("/config"):
            return
        try:
            payload = json.loads((msg.payload or b"{}").decode("utf-8", errors="ignore") or "{}")
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        parsed = self._parse_discovery_topic(topic)
        if not parsed:
            return
        component, unique_id = parsed
        if not self._looks_like_tasmota(topic, payload):
            return

        device = payload.get("device", {}) if isinstance(payload.get("device", {}), dict) else {}
        name = str(payload.get("name") or payload.get("object_id") or unique_id)
        identifiers = device.get("identifiers") or []
        if isinstance(identifiers, str):
            identifiers = [identifiers]
        base_id = self._normalize_id(unique_id, identifiers)
        dev_id = f"tasmota_{base_id}"

        dtype = self._infer_dtype(component)
        address = str(payload.get("state_topic") or payload.get("command_topic") or topic)
        dev = self.registry.get(dev_id)
        if not dev:
            dev = IoTDevice(dev_id, dtype, "mqtt", address, name)
            self.registry.register(dev)
        else:
            dev.name = name or dev.name
            dev.address = address or dev.address
            dev.online = True
            dev.last_seen = time.time()
            self.registry.save()

        with self._lock:
            self._discovered_components[dev_id].add(component)
            known_components = sorted(self._discovered_components[dev_id])

        device_meta = {
            "component": component,
            "state_topic": payload.get("state_topic"),
            "command_topic": payload.get("command_topic"),
            "manufacturer": device.get("manufacturer") if isinstance(device, dict) else "",
            "model": device.get("model") if isinstance(device, dict) else "",
            "sw": payload.get("sw") or (device.get("sw_version") if isinstance(device, dict) else ""),
            "ha_topic": topic,
            "components": known_components,
        }
        for key, val in device_meta.items():
            if val is not None and val != "":
                dev.update(key, val)

        self._upsert_sqlite(dev=dev, component=component, source_topic=topic, payload=payload)
        log.info("Tasmota discovered: %s component=%s", dev_id, component)

    def _parse_discovery_topic(self, topic: str) -> tuple[str, str] | None:
        parts = [p for p in topic.split("/") if p]
        # Формат Home Assistant discovery: homeassistant/<component>/<unique_id>/config
        if len(parts) < 4:
            return None
        component = parts[1]
        unique_id = parts[-2]
        if not component or not unique_id:
            return None
        return component, unique_id

    def _looks_like_tasmota(self, topic: str, payload: dict) -> bool:
        low_topic = topic.lower()
        if "tasmota" in low_topic:
            return True

        text_fields = []
        for key in ("state_topic", "command_topic", "name", "uniq_id", "unique_id", "sw"):
            val = payload.get(key)
            if isinstance(val, str):
                text_fields.append(val.lower())

        device = payload.get("device", {}) if isinstance(payload.get("device", {}), dict) else {}
        for key in ("manufacturer", "model", "name", "sw_version"):
            val = device.get(key)
            if isinstance(val, str):
                text_fields.append(val.lower())

        identifiers = device.get("identifiers") or []
        if isinstance(identifiers, str):
            identifiers = [identifiers]
        text_fields.extend([str(x).lower() for x in identifiers])

        markers = ("tasmota", "sonoff", "tuya")
        return any(any(m in field for m in markers) for field in text_fields)

    def _normalize_id(self, unique_id: str, identifiers: list[str]) -> str:
        raw = ""
        if identifiers:
            raw = str(identifiers[0])
        if not raw:
            raw = str(unique_id or "unknown")
        return "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_").lower() or "unknown"

    def _infer_dtype(self, component: str) -> str:
        actuator_components = {"switch", "light", "fan", "cover", "button", "number", "select"}
        if (component or "").lower() in actuator_components:
            return "actuator"
        return "sensor"

    def _upsert_sqlite(self, dev: IoTDevice, component: str, source_topic: str, payload: dict):
        ts = time.time()
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """
                INSERT INTO iot_devices (
                    device_id, name, protocol, dtype, address,
                    source_topic, component, payload_json, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name=excluded.name,
                    protocol=excluded.protocol,
                    dtype=excluded.dtype,
                    address=excluded.address,
                    source_topic=excluded.source_topic,
                    component=excluded.component,
                    payload_json=excluded.payload_json,
                    last_seen=excluded.last_seen
            """,
                (
                    dev.id,
                    dev.name,
                    dev.protocol,
                    dev.type,
                    dev.address,
                    source_topic,
                    component,
                    json.dumps(payload, ensure_ascii=False),
                    ts,
                    ts,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning("TasmotaDiscovery SQLite upsert error: %s", e)

    def status(self) -> str:
        return "🟢 Tasmota Discovery подключён" if self._connected else "🔴 Tasmota Discovery отключён"


# ══════════════════════════════════════════════════════════
# ГЛАВНЫЙ КЛАСС IoTBridge
# ══════════════════════════════════════════════════════════


class IoTBridge:
    def __init__(self):
        self.registry = IoTRegistry()
        self.zigbee = ZigbeeAdapter(self.registry)
        self.lora = LoRaAdapter(self.registry)
        self.mesh = MeshAdapter(self.registry)
        self.mqtt = MQTTBroker(self.registry)
        self.modbus = ModbusAdapter(self.registry)
        self.tasmota = TasmotaDiscoveryBridge(self.registry)
        self._init_tasmota_discovery()
        log.info("IoTBridge инициализирован. Устройств: %d", len(self.registry.all()))

    def _init_tasmota_discovery(self):
        enabled = (os.getenv("ARGOS_TASMOTA_DISCOVERY", "on") or "on").strip().lower() not in {
            "0",
            "off",
            "false",
            "no",
            "нет",
        }
        if not enabled:
            log.info("Tasmota Discovery: OFF")
            return
        host = (os.getenv("ARGOS_TASMOTA_MQTT_HOST", "localhost") or "localhost").strip()
        try:
            port = int(os.getenv("ARGOS_TASMOTA_MQTT_PORT", "1883") or "1883")
        except Exception:
            port = 1883
        topic = (os.getenv("ARGOS_TASMOTA_DISCOVERY_TOPIC", "homeassistant/#") or "homeassistant/#").strip()
        result = self.tasmota.connect(host=host, port=port, topic=topic)
        if result.startswith("❌"):
            log.warning("Tasmota Discovery: %s", result)
        else:
            log.info("Tasmota Discovery: ON")

    def connect_zigbee(self, host="localhost", port=1883) -> str:
        return self.zigbee.connect_mqtt(host, port)

    def connect_lora(self, port="/dev/ttyUSB0", baud=9600) -> str:
        return self.lora.connect(port, baud)

    def start_mesh(self) -> str:
        return self.mesh.start()

    def connect_mqtt(self, host="localhost", port=1883) -> str:
        return self.mqtt.connect(host, port)

    def connect_modbus_serial(self, port="/dev/ttyUSB0", baud=9600) -> str:
        return self.modbus.connect_serial(port=port, baudrate=baud)

    def connect_modbus_tcp(self, host="127.0.0.1", port=502) -> str:
        return self.modbus.connect_tcp(host=host, port=port)

    def modbus_read(self, address: int, count: int = 1, unit: int = 1) -> str:
        return self.modbus.read_holding(address=address, count=count, unit=unit)

    def modbus_write(self, address: int, value: int, unit: int = 1) -> str:
        return self.modbus.write_register(address=address, value=value, unit=unit)

    def connect_tasmota_discovery(self, host="localhost", port=1883, topic="homeassistant/#") -> str:
        return self.tasmota.connect(host, port, topic)

    def register_device(self, dev_id: str, dtype: str, protocol: str, address: str = "", name: str = "") -> str:
        dev = IoTDevice(dev_id, dtype, protocol, address, name)
        return self.registry.register(dev)

    @staticmethod
    def _normalize_mac(value: str) -> str:
        raw = "".join(ch for ch in str(value or "") if ch.isalnum()).upper()
        if len(raw) != 12:
            return str(value or "").strip().upper()
        return ":".join(raw[i : i + 2] for i in range(0, 12, 2))

    def register_gateway(
        self, dev_id: str, protocol: str = "zigbee", ip: str = "", mac: str = "", name: str = ""
    ) -> str:
        gateway_id = (dev_id or "").strip() or f"gw_{int(time.time())}"
        normalized_mac = self._normalize_mac(mac) if mac else ""
        address = (ip or normalized_mac or "").strip()

        dev = IoTDevice(gateway_id, "gateway", protocol, address, name or gateway_id)
        if ip:
            dev.update("ip", ip.strip())
        if normalized_mac:
            dev.update("mac", normalized_mac)
        dev.update("gateway_protocol", protocol)
        return self.registry.register(dev)

    def _find_device(self, query: str) -> IoTDevice | None:
        q = (query or "").strip()
        if not q:
            return None

        direct = self.registry.get(q)
        if direct:
            return direct

        q_lower = q.lower()
        q_mac = self._normalize_mac(q)

        for dev in self.registry.all():
            if (dev.name or "").lower() == q_lower:
                return dev
            if (dev.address or "").lower() == q_lower:
                return dev

            ip = str(dev.state.get("ip", "") or "").strip().lower()
            if ip and ip == q_lower:
                return dev

            mac = self._normalize_mac(str(dev.state.get("mac", "") or ""))
            if mac and mac == q_mac:
                return dev
        return None

    def status(self) -> str:
        return self.registry.report()

    def capability_report(self) -> str:
        """Показывает фактические возможности IoT-стека на текущей ноде."""

        def has(mod: str) -> bool:
            try:
                return importlib.util.find_spec(mod) is not None
            except Exception:
                return False

        rows = [
            ("Zigbee (MQTT)", "IMPLEMENTED", "READY" if has("paho.mqtt.client") else "MISSING dep: paho-mqtt"),
            ("LoRa (UART AT)", "IMPLEMENTED", "READY" if has("serial") else "MISSING dep: pyserial"),
            ("WiFi Mesh (UDP)", "IMPLEMENTED", "READY"),
            ("MQTT Broker Bridge", "IMPLEMENTED", "READY" if has("paho.mqtt.client") else "MISSING dep: paho-mqtt"),
            ("Tasmota Discovery", "IMPLEMENTED", "READY" if has("paho.mqtt.client") else "MISSING dep: paho-mqtt"),
            ("Modbus RTU/TCP", "TEMPLATE-BASED", "Gateway templates + external runtime"),
            ("BACnet", "IMPLEMENTED", "Adapter available via src.connectivity.bacnet_bridge.BACnetBridge"),
            ("KNX", "PLANNED/TEMPLATE", "Protocol listed; adapter code not implemented in IoTBridge"),
            ("LonWorks", "PLANNED/TEMPLATE", "Protocol listed; adapter code not implemented in IoTBridge"),
            ("M-Bus", "PLANNED/TEMPLATE", "Protocol listed; adapter code not implemented in IoTBridge"),
            ("OPC UA", "PLANNED/TEMPLATE", "Protocol listed; adapter code not implemented in IoTBridge"),
        ]

        lines = ["📡 IOT ВОЗМОЖНОСТИ (фактическая матрица):"]
        for name, status, note in rows:
            icon = "✅" if status == "IMPLEMENTED" else "🟨" if status == "TEMPLATE-BASED" else "🧭"
            lines.append(f"  {icon} {name}: {status} — {note}")

        lines.append("\nАвтодобавление устройств:")
        lines.append("  • Zigbee: через MQTT топики zigbee2mqtt/#")
        lines.append("  • LoRa: через входящие пакеты +RCV")
        lines.append("  • Mesh: через UDP-пакеты mesh")
        lines.append("  • Tasmota: через homeassistant/# discovery")
        lines.append("\nАвторасширение шаблонов:")
        lines.append("  • изучи протокол [шаблон] [протокол] [прошивка?] [описание?]")
        lines.append("  • изучи устройство [шаблон] [протокол] [hardware?]")

        lines.append("\nПоддерживаемые Zigbee-шлюзы (экосистемные хабы):")
        for model in SUPPORTED_ZIGBEE_HUBS:
            lines.append(f"  • {model}")

        lines.append("\nПоддерживаемые Zigbee-координаторы (стики/адаптеры):")
        for model in SUPPORTED_ZIGBEE_COORDINATORS:
            lines.append(f"  • {model}")
        return "\n".join(lines)

    def get_capabilities(self) -> str:
        """Совместимость с core-командой iot возможности."""
        return self.capability_report()

    def device_status(self, dev_id: str) -> str:
        dev = self._find_device(dev_id)
        if not dev:
            return f"❌ Устройство '{dev_id}' не найдено."

        status = "🟢 online" if dev.online else "🔴 offline"
        lines = [
            f"📟 Устройство: {dev.name}",
            f"  id: {dev.id}",
            f"  тип: {dev.type}",
            f"  протокол: {dev.protocol}",
            f"  адрес: {dev.address or '—'}",
            f"  статус: {status}",
            f"  last_seen: {_ago(dev.last_seen)}",
        ]
        if dev.state:
            lines.append("  данные:")
            for k, v in list(dev.state.items())[:20]:
                lines.append(f"    - {k}: {v}")
        else:
            lines.append("  данные: нет")
        return "\n".join(lines)

    def send_command(self, dev_id: str, command: str, value=None) -> str:
        dev = self._find_device(dev_id)
        if not dev:
            return f"❌ Устройство '{dev_id}' не найдено."
        if dev.protocol == "zigbee":
            return self.zigbee.send_command(dev.address, {command: value})
        if dev.protocol == "lora":
            return self.lora.send(dev.address, f"{command}:{value}")
        if dev.protocol == "mesh":
            return self.mesh.send(dev.address, {"cmd": command, "val": value})
        if dev.protocol == "mqtt":
            return self.mqtt.publish(f"devices/{dev_id}/set", {command: value})
        if dev.protocol == "modbus":
            c = (command or "").strip().lower()
            if c in {"read", "read_holding", "чтение"}:
                try:
                    addr = int(value) if value is not None else 0
                    return self.modbus_read(address=addr, count=1, unit=1)
                except Exception:
                    return "Формат для modbus read: команда устройству [id] read [address]"
            if c in {"write", "write_register", "запись"}:
                return "Формат для modbus write: modbus запись [address] [value] [unit]"
        return f"❌ Протокол '{dev.protocol}' не поддерживает команды."

    def get_value(self, dev_id: str, key: str):
        dev = self._find_device(dev_id)
        if not dev:
            return None
        return dev.state.get(key)
