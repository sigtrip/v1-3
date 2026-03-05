"""
bacnet_bridge.py — BACnet IoT-протокол мост для Аргоса.

Поддерживает:
  - Обнаружение BACnet-устройств (WhoIs / IAm)
  - Чтение свойств (ReadProperty)
  - Запись свойств (WriteProperty)
  - Статус подключённых устройств

Зависимость: BACSim / bacpypes3 (graceful degradation при отсутствии).
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from src.argos_logger import get_logger

log = get_logger("argos.bacnet")

# ── Graceful import ──────────────────────────────────────
try:
    from bacpypes3.apdu import (
        ReadPropertyRequest,
        WhoIsRequest,
        WritePropertyRequest,
    )
    from bacpypes3.app import BIPSimpleApplication
    from bacpypes3.basetypes import PropertyIdentifier
    from bacpypes3.local.device import DeviceObject
    from bacpypes3.pdu import Address
    from bacpypes3.primitivedata import ObjectIdentifier, Real, Unsigned

    BACPYPES_OK = True
except ImportError:
    BACPYPES_OK = False

# ── Fallback stub когда bacpypes3 нет ────────────────────
_BACNET_DEFAULT_PORT = int(os.getenv("ARGOS_BACNET_PORT", "47808"))
_BACNET_DEFAULT_IP = os.getenv("ARGOS_BACNET_IP", "0.0.0.0")
_BACNET_DEVICE_ID = int(os.getenv("ARGOS_BACNET_DEVICE_ID", "599"))
_BACNET_DEVICE_NAME = os.getenv("ARGOS_BACNET_DEVICE_NAME", "Argos-BACnet-GW")


class BACnetDevice:
    """Обнаруженное BACnet-устройство."""

    def __init__(self, device_id: int, address: str, name: str = "", vendor: str = "", model: str = ""):
        self.device_id = device_id
        self.address = address
        self.name = name or f"BACnet-{device_id}"
        self.vendor = vendor
        self.model = model
        self.last_seen = time.time()
        self.properties: dict[str, Any] = {}

    def as_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "address": self.address,
            "name": self.name,
            "vendor": self.vendor,
            "model": self.model,
            "last_seen": self.last_seen,
            "properties": self.properties,
        }


class BACnetBridge:
    """
    BACnet-мост Аргоса.

    Если bacpypes3 не установлен — работает в simulation-mode:
    можно регистрировать устройства вручную и отслеживать статус.
    """

    def __init__(self, ip: str | None = None, port: int | None = None, device_id: int | None = None):
        self.ip = ip or _BACNET_DEFAULT_IP
        self.port = port or _BACNET_DEFAULT_PORT
        self.device_id = device_id or _BACNET_DEVICE_ID
        self.device_name = _BACNET_DEVICE_NAME
        self.devices: dict[int, BACnetDevice] = {}
        self._app = None
        self._running = False
        self._lock = threading.Lock()
        self.simulation = not BACPYPES_OK

        if BACPYPES_OK:
            try:
                self._init_bacpypes()
            except Exception as exc:
                log.warning("BACnet: не удалось инициализировать bacpypes3: %s", exc)
                self.simulation = True

        mode = "simulation" if self.simulation else "live"
        log.info("BACnet Bridge: %s (ip=%s port=%d id=%d)", mode, self.ip, self.port, self.device_id)

    # ── Инициализация bacpypes3 ──────────────────────────
    def _init_bacpypes(self):
        """Создаёт BACnet-приложение через bacpypes3."""
        device = DeviceObject(
            objectIdentifier=("device", self.device_id),
            objectName=self.device_name,
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=999,
        )
        self._app = BIPSimpleApplication(device, f"{self.ip}:{self.port}")
        log.info("BACnet: bacpypes3 BIP app создано")

    # ── Обнаружение устройств (WhoIs) ────────────────────
    def scan(self, low_limit: int = 0, high_limit: int = 4194303, timeout: float = 5.0) -> str:
        """Отправляет WhoIs и собирает IAm-ответы."""
        if self.simulation:
            return self._sim_scan()

        try:
            import asyncio

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._async_scan(low_limit, high_limit, timeout))
            loop.close()
            return result
        except Exception as exc:
            log.error("BACnet scan: %s", exc)
            return f"❌ BACnet scan ошибка: {exc}"

    async def _async_scan(self, low: int, high: int, timeout: float) -> str:
        """Асинхронный WhoIs через bacpypes3."""
        request = WhoIsRequest(
            deviceInstanceRangeLowLimit=low,
            deviceInstanceRangeHighLimit=high,
        )
        request.pduDestination = Address("255.255.255.255")

        discovered = []
        try:
            responses = await self._app.who_is(low, high)
            for resp in responses:
                dev_id = resp.iAmDeviceIdentifier[1]
                addr = str(resp.pduSource)
                dev = BACnetDevice(dev_id, addr)
                with self._lock:
                    self.devices[dev_id] = dev
                discovered.append(f"  #{dev_id} @ {addr}")
        except Exception as exc:
            return f"❌ BACnet WhoIs ошибка: {exc}"

        if not discovered:
            return "🔍 BACnet: устройства не обнаружены."
        return f"🔍 BACnet: найдено {len(discovered)} устройств:\n" + "\n".join(discovered)

    def _sim_scan(self) -> str:
        """Simulation-mode scan: возвращает зарегистрированные устройства."""
        if not self.devices:
            return "🔍 BACnet (sim): устройств не зарегистрировано. Добавьте через register_device()."
        lines = [f"🔍 BACnet (sim): {len(self.devices)} устройств:"]
        for dev in self.devices.values():
            lines.append(f"  #{dev.device_id} [{dev.name}] @ {dev.address}")
        return "\n".join(lines)

    # ── Чтение свойства ──────────────────────────────────
    def read_property(self, device_id: int, obj_type: str, obj_instance: int, prop_name: str) -> str:
        """Чтение свойства BACnet-объекта."""
        if self.simulation:
            return self._sim_read(device_id, obj_type, obj_instance, prop_name)

        try:
            import asyncio

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._async_read(device_id, obj_type, obj_instance, prop_name))
            loop.close()
            return result
        except Exception as exc:
            log.error("BACnet read: %s", exc)
            return f"❌ BACnet read ошибка: {exc}"

    async def _async_read(self, device_id: int, obj_type: str, obj_instance: int, prop_name: str) -> str:
        dev = self.devices.get(device_id)
        if not dev:
            return f"❌ Устройство #{device_id} не найдено. Сначала выполните scan."

        try:
            obj_id = ObjectIdentifier((obj_type, obj_instance))
            prop_id = PropertyIdentifier(prop_name)
            request = ReadPropertyRequest(
                objectIdentifier=obj_id,
                propertyIdentifier=prop_id,
            )
            request.pduDestination = Address(dev.address)
            response = await self._app.request(request)
            value = response.propertyValue.cast_out()
            dev.properties[f"{obj_type}:{obj_instance}:{prop_name}"] = value
            return f"📖 BACnet #{device_id} {obj_type}:{obj_instance}.{prop_name} = {value}"
        except Exception as exc:
            return f"❌ BACnet read #{device_id}: {exc}"

    def _sim_read(self, device_id: int, obj_type: str, obj_instance: int, prop_name: str) -> str:
        dev = self.devices.get(device_id)
        if not dev:
            return f"❌ Устройство #{device_id} не найдено."
        key = f"{obj_type}:{obj_instance}:{prop_name}"
        val = dev.properties.get(key, "N/A (simulation)")
        return f"📖 BACnet (sim) #{device_id} {key} = {val}"

    # ── Запись свойства ──────────────────────────────────
    def write_property(self, device_id: int, obj_type: str, obj_instance: int, prop_name: str, value: Any) -> str:
        """Запись значения в свойство BACnet-объекта."""
        if self.simulation:
            return self._sim_write(device_id, obj_type, obj_instance, prop_name, value)

        try:
            import asyncio

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self._async_write(device_id, obj_type, obj_instance, prop_name, value))
            loop.close()
            return result
        except Exception as exc:
            log.error("BACnet write: %s", exc)
            return f"❌ BACnet write ошибка: {exc}"

    async def _async_write(self, device_id: int, obj_type: str, obj_instance: int, prop_name: str, value: Any) -> str:
        dev = self.devices.get(device_id)
        if not dev:
            return f"❌ Устройство #{device_id} не найдено."

        try:
            obj_id = ObjectIdentifier((obj_type, obj_instance))
            prop_id = PropertyIdentifier(prop_name)
            request = WritePropertyRequest(
                objectIdentifier=obj_id,
                propertyIdentifier=prop_id,
            )
            request.pduDestination = Address(dev.address)
            request.propertyValue = Real(float(value))
            await self._app.request(request)
            dev.properties[f"{obj_type}:{obj_instance}:{prop_name}"] = value
            return f"✅ BACnet #{device_id} {obj_type}:{obj_instance}.{prop_name} ← {value}"
        except Exception as exc:
            return f"❌ BACnet write #{device_id}: {exc}"

    def _sim_write(self, device_id: int, obj_type: str, obj_instance: int, prop_name: str, value: Any) -> str:
        dev = self.devices.get(device_id)
        if not dev:
            return f"❌ Устройство #{device_id} не найдено."
        key = f"{obj_type}:{obj_instance}:{prop_name}"
        dev.properties[key] = value
        return f"✅ BACnet (sim) #{device_id} {key} ← {value}"

    # ── Регистрация устройства вручную ───────────────────
    def register_device(self, device_id: int, address: str, name: str = "", vendor: str = "", model: str = "") -> str:
        dev = BACnetDevice(device_id, address, name, vendor, model)
        with self._lock:
            self.devices[device_id] = dev
        log.info("BACnet: зарегистрировано устройство #%d @ %s", device_id, address)
        return f"✅ BACnet устройство #{device_id} [{dev.name}] зарегистрировано @ {address}"

    # ── Удаление устройства ──────────────────────────────
    def remove_device(self, device_id: int) -> str:
        with self._lock:
            if device_id in self.devices:
                del self.devices[device_id]
                return f"✅ BACnet устройство #{device_id} удалено."
        return f"❌ Устройство #{device_id} не найдено."

    # ── Статус ───────────────────────────────────────────
    def status(self) -> str:
        mode = "simulation" if self.simulation else "live (bacpypes3)"
        lines = [
            f"🏢 BACnet Bridge — {mode}",
            f"   IP: {self.ip}:{self.port}  Device ID: {self.device_id}",
            f"   Устройств: {len(self.devices)}",
        ]
        if self.devices:
            lines.append("   Устройства:")
            for dev in self.devices.values():
                age = time.time() - dev.last_seen
                lines.append(
                    f"     #{dev.device_id} [{dev.name}] @ {dev.address}"
                    f"  (vendor={dev.vendor or '?'}, seen {age:.0f}s ago)"
                )
        return "\n".join(lines)

    def device_count(self) -> int:
        return len(self.devices)

    def as_dict(self) -> dict:
        return {
            "mode": "simulation" if self.simulation else "live",
            "ip": self.ip,
            "port": self.port,
            "device_id": self.device_id,
            "device_count": len(self.devices),
            "devices": {did: d.as_dict() for did, d in self.devices.items()},
        }
