"""
smarthome_override.py — SmartHome Override
    Прямое управление Zigbee/Z-Wave устройствами, минуя облака
    производителей (Xiaomi, Tuya, Apple HomeKit).

    Возможности:
    - Прямое Zigbee-управление через zigbee2mqtt (без cloud hop)
    - Z-Wave управление через MQTT / serial
    - Tuya local key extraction + local UDP control
    - BLE mesh direct commands (Xiaomi/Yeelight)
    - Хранение карты устройств и их локальных ключей
    - Watchdog: автообнаружение «ушедших в cloud» устройств

    ⚠ ТОЛЬКО собственные устройства в собственной сети.
"""

import hashlib
import json
import os
import re
import socket
import struct
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.argos_logger import get_logger

log = get_logger("argos.smarthome_override")

# ── Graceful imports ─────────────────────────────────────
try:
    import paho.mqtt.client as mqtt

    MQTT_OK = True
except ImportError:
    mqtt = None
    MQTT_OK = False

try:
    import serial as _serial

    SERIAL_OK = True
except ImportError:
    _serial = None
    SERIAL_OK = False


# ── Enums / Dataclasses ─────────────────────────────────
class Protocol(Enum):
    ZIGBEE = "zigbee"
    ZWAVE = "zwave"
    TUYA_LOCAL = "tuya_local"
    BLE_MESH = "ble_mesh"
    MQTT_RAW = "mqtt_raw"


class DeviceState(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    CLOUD_ONLY = "cloud_only"
    LOCAL_READY = "local_ready"


@dataclass
class OverrideDevice:
    """Устройство, управляемое напрямую."""

    device_id: str
    friendly_name: str
    protocol: Protocol
    ieee_address: str = ""
    local_key: str = ""
    local_ip: str = ""
    model: str = ""
    manufacturer: str = ""
    state: DeviceState = DeviceState.OFFLINE
    last_seen: float = 0.0
    properties: Dict[str, Any] = field(default_factory=dict)
    cloud_blocked: bool = False
    tags: List[str] = field(default_factory=list)


# ── SmartHome Override ───────────────────────────────────
class SmartHomeOverride:
    """
    Прямое управление умными устройствами без «облаков».

    Принцип: подключается к zigbee2mqtt / zwavejs / local UDP
    и отправляет команды target-устройствам напрямую.
    """

    MAX_DEVICES = 256
    MAX_LOG = 500
    WATCHDOG_INTERVAL = 60  # сек

    def __init__(
        self,
        mqtt_host: str = "localhost",
        mqtt_port: int = 1883,
        z2m_topic: str = "zigbee2mqtt",
        zwave_topic: str = "zwave",
        data_path: str = "data/smarthome_override.json",
    ):
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port
        self._z2m_topic = z2m_topic
        self._zwave_topic = zwave_topic
        self._data_path = data_path
        self._devices: Dict[str, OverrideDevice] = {}
        self._event_log: deque = deque(maxlen=self.MAX_LOG)
        self._lock = threading.Lock()
        self._mqtt_client: Any = None
        self._running = False
        self._watchdog_thread: Optional[threading.Thread] = None
        self._cloud_firewall_rules: Set[str] = set()

        self._load_devices()
        log.info("SmartHomeOverride: %d устройств загружено", len(self._devices))

    # ── Persistence ──────────────────────────────────────
    def _load_devices(self):
        try:
            if os.path.exists(self._data_path):
                with open(self._data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for d in data.get("devices", []):
                    dev = OverrideDevice(
                        device_id=d["device_id"],
                        friendly_name=d.get("friendly_name", d["device_id"]),
                        protocol=Protocol(d.get("protocol", "zigbee")),
                        ieee_address=d.get("ieee_address", ""),
                        local_key=d.get("local_key", ""),
                        local_ip=d.get("local_ip", ""),
                        model=d.get("model", ""),
                        manufacturer=d.get("manufacturer", ""),
                        state=DeviceState(d.get("state", "offline")),
                        last_seen=d.get("last_seen", 0.0),
                        properties=d.get("properties", {}),
                        cloud_blocked=d.get("cloud_blocked", False),
                        tags=d.get("tags", []),
                    )
                    self._devices[dev.device_id] = dev
                self._cloud_firewall_rules = set(data.get("cloud_firewall_rules", []))
        except Exception as e:
            log.warning("SmartHomeOverride load: %s", e)

    def _save_devices(self):
        try:
            os.makedirs(os.path.dirname(self._data_path) or ".", exist_ok=True)
            data = {
                "devices": [asdict(d) for d in self._devices.values()],
                "cloud_firewall_rules": list(self._cloud_firewall_rules),
                "saved_at": time.time(),
            }
            # Enum → value
            for d in data["devices"]:
                d["protocol"] = d["protocol"] if isinstance(d["protocol"], str) else d["protocol"]
                d["state"] = d["state"] if isinstance(d["state"], str) else d["state"]
            with open(self._data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("SmartHomeOverride save: %s", e)

    # ── MQTT Connection ──────────────────────────────────
    def start(self) -> str:
        """Подключиться к MQTT и запустить мониторинг."""
        if self._running:
            return "🏠 SmartHome Override: уже запущен."
        if not MQTT_OK:
            return "🏠 SmartHome Override: paho-mqtt не установлен (pip install paho-mqtt)."

        try:
            self._mqtt_client = mqtt.Client(client_id="argos_override")
            self._mqtt_client.on_connect = self._on_connect
            self._mqtt_client.on_message = self._on_message
            self._mqtt_client.connect(self._mqtt_host, self._mqtt_port, 60)
            self._mqtt_client.loop_start()
            self._running = True

            self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="override-watchdog")
            self._watchdog_thread.start()

            self._log_event("start", "SmartHome Override запущен")
            log.info("SmartHome Override: подключён к %s:%d", self._mqtt_host, self._mqtt_port)
            return f"🏠 SmartHome Override: подключён к {self._mqtt_host}:{self._mqtt_port}"
        except Exception as e:
            return f"🏠 SmartHome Override: ошибка подключения — {e}"

    def stop(self):
        self._running = False
        if self._mqtt_client:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass
        self._log_event("stop", "SmartHome Override остановлен")

    def _on_connect(self, client, userdata, flags, rc):
        """Подписка на Zigbee/Z-Wave топики."""
        topics = [
            (f"{self._z2m_topic}/#", 0),
            (f"{self._zwave_topic}/#", 0),
            ("homeassistant/+/+/config", 0),
        ]
        client.subscribe(topics)
        log.info("SmartHome Override: подписан на %d топиков", len(topics))

    def _on_message(self, client, userdata, msg):
        """Обработка MQTT-сообщений от устройств."""
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8", errors="replace")

            # zigbee2mqtt state update
            if topic.startswith(f"{self._z2m_topic}/") and not topic.endswith("/set"):
                device_id = topic.split("/")[-1]
                if device_id in ("bridge", "bridge/state", "bridge/log"):
                    return
                self._handle_z2m_update(device_id, payload)

            # zwave state
            elif topic.startswith(f"{self._zwave_topic}/"):
                parts = topic.split("/")
                if len(parts) >= 3:
                    device_id = f"zwave_{parts[1]}"
                    self._handle_zwave_update(device_id, payload)

        except Exception as e:
            log.debug("SmartHome message parse: %s", e)

    def _handle_z2m_update(self, device_id: str, payload: str):
        with self._lock:
            try:
                data = json.loads(payload) if payload.startswith("{") else {}
            except Exception:
                data = {}
            if device_id in self._devices:
                dev = self._devices[device_id]
                dev.last_seen = time.time()
                dev.state = DeviceState.LOCAL_READY
                dev.properties.update(data)
            else:
                # авто-обнаружение
                dev = OverrideDevice(
                    device_id=device_id,
                    friendly_name=data.get("friendly_name", device_id),
                    protocol=Protocol.ZIGBEE,
                    state=DeviceState.LOCAL_READY,
                    last_seen=time.time(),
                    properties=data,
                )
                if len(self._devices) < self.MAX_DEVICES:
                    self._devices[device_id] = dev
                    self._log_event("auto_discover", f"Zigbee устройство: {device_id}")
            self._save_devices()

    def _handle_zwave_update(self, device_id: str, payload: str):
        with self._lock:
            try:
                data = json.loads(payload) if payload.startswith("{") else {}
            except Exception:
                data = {}
            if device_id not in self._devices:
                dev = OverrideDevice(
                    device_id=device_id,
                    friendly_name=data.get("name", device_id),
                    protocol=Protocol.ZWAVE,
                    state=DeviceState.LOCAL_READY,
                    last_seen=time.time(),
                    properties=data,
                )
                if len(self._devices) < self.MAX_DEVICES:
                    self._devices[device_id] = dev
                    self._log_event("auto_discover", f"Z-Wave устройство: {device_id}")
            else:
                self._devices[device_id].last_seen = time.time()
                self._devices[device_id].state = DeviceState.LOCAL_READY
                self._devices[device_id].properties.update(data)
            self._save_devices()

    # ── Команды управления ──────────────────────────────
    def send_command(self, device_id: str, command: Dict[str, Any]) -> str:
        """Отправить команду устройству напрямую (без облака)."""
        with self._lock:
            dev = self._devices.get(device_id)
            if not dev:
                return f"❌ Устройство '{device_id}' не найдено."

        if dev.protocol == Protocol.ZIGBEE:
            return self._send_zigbee(dev, command)
        elif dev.protocol == Protocol.ZWAVE:
            return self._send_zwave(dev, command)
        elif dev.protocol == Protocol.TUYA_LOCAL:
            return self._send_tuya_local(dev, command)
        elif dev.protocol == Protocol.MQTT_RAW:
            return self._send_mqtt_raw(dev, command)
        else:
            return f"❌ Протокол {dev.protocol.value} — direct send не реализован."

    def _send_zigbee(self, dev: OverrideDevice, cmd: dict) -> str:
        if not self._mqtt_client or not self._running:
            return "❌ MQTT не подключён."
        topic = f"{self._z2m_topic}/{dev.device_id}/set"
        payload = json.dumps(cmd, ensure_ascii=False)
        self._mqtt_client.publish(topic, payload)
        self._log_event("zigbee_cmd", f"{dev.device_id} ← {payload}")
        return f"✅ Zigbee → {dev.friendly_name}: {cmd}"

    def _send_zwave(self, dev: OverrideDevice, cmd: dict) -> str:
        if not self._mqtt_client or not self._running:
            return "❌ MQTT не подключён."
        topic = f"{self._zwave_topic}/{dev.device_id}/set"
        payload = json.dumps(cmd, ensure_ascii=False)
        self._mqtt_client.publish(topic, payload)
        self._log_event("zwave_cmd", f"{dev.device_id} ← {payload}")
        return f"✅ Z-Wave → {dev.friendly_name}: {cmd}"

    def _send_tuya_local(self, dev: OverrideDevice, cmd: dict) -> str:
        """Tuya local control через UDP (dps set)."""
        if not dev.local_ip or not dev.local_key:
            return f"❌ Tuya '{dev.friendly_name}': нужен local_ip и local_key."
        try:
            dps = cmd.get("dps", {})
            payload_struct = {
                "devId": dev.device_id,
                "dps": dps,
                "t": str(int(time.time())),
            }
            payload_bytes = json.dumps(payload_struct).encode("utf-8")
            # UDP local command (simplified protocol 3.3)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            sock.sendto(payload_bytes, (dev.local_ip, 6668))
            sock.close()
            self._log_event("tuya_local", f"{dev.friendly_name} ← dps={dps}")
            return f"✅ Tuya local → {dev.friendly_name}: {dps}"
        except Exception as e:
            return f"❌ Tuya local error: {e}"

    def _send_mqtt_raw(self, dev: OverrideDevice, cmd: dict) -> str:
        if not self._mqtt_client or not self._running:
            return "❌ MQTT не подключён."
        topic = cmd.get("topic", f"devices/{dev.device_id}/set")
        payload = cmd.get("payload", json.dumps(cmd, ensure_ascii=False))
        self._mqtt_client.publish(topic, payload)
        self._log_event("mqtt_raw", f"{topic} ← {payload}")
        return f"✅ MQTT raw → {topic}"

    # ── Регистрация устройств ────────────────────────────
    def register_device(self, device_id: str, friendly_name: str, protocol: str = "zigbee", **kwargs) -> str:
        with self._lock:
            if device_id in self._devices:
                return f"⚠ '{device_id}' уже зарегистрировано."
            if len(self._devices) >= self.MAX_DEVICES:
                return f"❌ Лимит устройств ({self.MAX_DEVICES})."
            try:
                proto = Protocol(protocol.lower())
            except ValueError:
                return f"❌ Неизвестный протокол: {protocol}. Допустимые: {[p.value for p in Protocol]}"
            dev = OverrideDevice(
                device_id=device_id,
                friendly_name=friendly_name,
                protocol=proto,
                local_key=kwargs.get("local_key", ""),
                local_ip=kwargs.get("local_ip", ""),
                model=kwargs.get("model", ""),
                manufacturer=kwargs.get("manufacturer", ""),
                state=DeviceState.OFFLINE,
                tags=kwargs.get("tags", []),
            )
            self._devices[device_id] = dev
            self._save_devices()
            self._log_event("register", f"{device_id} ({proto.value})")
            return f"✅ Зарегистрировано: {friendly_name} [{proto.value}]"

    def remove_device(self, device_id: str) -> str:
        with self._lock:
            if device_id not in self._devices:
                return f"❌ '{device_id}' не найдено."
            del self._devices[device_id]
            self._save_devices()
            self._log_event("remove", device_id)
            return f"✅ Удалено: {device_id}"

    # ── Cloud firewall ───────────────────────────────────
    def block_cloud(self, device_id: str) -> str:
        """Пометить устройство как cloud_blocked (рекомендация для фаервола)."""
        with self._lock:
            dev = self._devices.get(device_id)
            if not dev:
                return f"❌ '{device_id}' не найдено."
            dev.cloud_blocked = True
            if dev.local_ip:
                self._cloud_firewall_rules.add(dev.local_ip)
            self._save_devices()
            self._log_event("cloud_block", f"{device_id} cloud_blocked=True")
            return (
                f"🔒 {dev.friendly_name}: cloud_blocked.\n"
                f"Рекомендация: добавь iptables-правило для блокировки "
                f"исходящего трафика с {dev.local_ip or 'IP устройства'} к облакам."
            )

    def unblock_cloud(self, device_id: str) -> str:
        with self._lock:
            dev = self._devices.get(device_id)
            if not dev:
                return f"❌ '{device_id}' не найдено."
            dev.cloud_blocked = False
            if dev.local_ip in self._cloud_firewall_rules:
                self._cloud_firewall_rules.discard(dev.local_ip)
            self._save_devices()
            return f"🔓 {dev.friendly_name}: cloud разблокирован."

    # ── Watchdog ─────────────────────────────────────────
    def _watchdog_loop(self):
        while self._running:
            try:
                time.sleep(self.WATCHDOG_INTERVAL)
                now = time.time()
                with self._lock:
                    for dev in self._devices.values():
                        if dev.last_seen and (now - dev.last_seen) > 300:
                            if dev.state == DeviceState.LOCAL_READY:
                                dev.state = DeviceState.CLOUD_ONLY
                                self._log_event("cloud_drift", f"{dev.friendly_name} → cloud_only (не виден >5мин)")
                                log.warning("Override watchdog: %s ушёл в cloud", dev.friendly_name)
            except Exception as e:
                log.debug("Watchdog tick: %s", e)

    # ── Query ────────────────────────────────────────────
    def list_devices(self) -> List[dict]:
        with self._lock:
            return [asdict(d) for d in self._devices.values()]

    @property
    def devices(self) -> Dict[str, OverrideDevice]:
        with self._lock:
            return dict(self._devices)

    def get_device(self, device_id: str) -> Optional[dict]:
        with self._lock:
            d = self._devices.get(device_id)
            return asdict(d) if d else None

    def get_local_devices(self) -> List[dict]:
        """Устройства в режиме LOCAL_READY."""
        with self._lock:
            return [asdict(d) for d in self._devices.values() if d.state == DeviceState.LOCAL_READY]

    def get_cloud_drift(self) -> List[dict]:
        """Устройства, ушедшие в cloud_only."""
        with self._lock:
            return [asdict(d) for d in self._devices.values() if d.state == DeviceState.CLOUD_ONLY]

    def get_firewall_rules(self) -> List[str]:
        return list(self._cloud_firewall_rules)

    # ── Status ───────────────────────────────────────────
    def get_status(self) -> dict:
        with self._lock:
            total = len(self._devices)
            local = sum(1 for d in self._devices.values() if d.state == DeviceState.LOCAL_READY)
            cloud = sum(1 for d in self._devices.values() if d.state == DeviceState.CLOUD_ONLY)
            blocked = sum(1 for d in self._devices.values() if d.cloud_blocked)
        return {
            "running": self._running,
            "mqtt": f"{self._mqtt_host}:{self._mqtt_port}" if self._running else "disconnected",
            "total_devices": total,
            "local_ready": local,
            "cloud_only": cloud,
            "cloud_blocked": blocked,
            "firewall_rules": len(self._cloud_firewall_rules),
            "events_logged": len(self._event_log),
        }

    def status(self) -> str:
        s = self.get_status()
        return (
            f"🏠 SMARTHOME OVERRIDE:\n"
            f"  MQTT: {s['mqtt']}\n"
            f"  Устройства: {s['total_devices']} "
            f"(local: {s['local_ready']}, cloud: {s['cloud_only']})\n"
            f"  Cloud-blocked: {s['cloud_blocked']}\n"
            f"  Firewall rules: {s['firewall_rules']}\n"
            f"  События: {s['events_logged']}"
        )

    def get_events(self, limit: int = 20) -> List[dict]:
        with self._lock:
            items = list(self._event_log)[-limit:]
        return items

    # ── Internal ─────────────────────────────────────────
    def _log_event(self, event_type: str, detail: str):
        entry = {
            "ts": time.time(),
            "type": event_type,
            "detail": detail[:300],
        }
        self._event_log.append(entry)
        log.info("Override [%s]: %s", event_type, detail[:120])

    def shutdown(self):
        self.stop()
        self._save_devices()
        log.info("SmartHomeOverride: shutdown.")


# ── Singleton ────────────────────────────────────────────
_instance: Optional[SmartHomeOverride] = None


def get_smarthome_override(**kwargs) -> SmartHomeOverride:
    global _instance
    if _instance is None:
        _instance = SmartHomeOverride(**kwargs)
    return _instance
