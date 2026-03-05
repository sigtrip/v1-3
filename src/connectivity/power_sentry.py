"""
power_sentry.py — Power Sentry
    Контроль энергосистемы: мониторинг ИБП, напряжение, потребление,
    аварийное отключение нагрузок.

    Поддержка:
    - NUT (Network UPS Tools) через upsc / socket API
    - USB HID UPS (через hidapi fallback)
    - APC Smart-UPS через serial
    - SNMP UPS (Eaton/CyberPower)
    - Ручные сенсоры (INA219/PZEM через serial)

    ⚠ Управление отключением — ТОЛЬКО по подтверждению администратора.
"""

import json
import os
import re
import socket
import subprocess
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.argos_logger import get_logger

log = get_logger("argos.power_sentry")

# ── Graceful imports ─────────────────────────────────────
try:
    import serial as _serial

    SERIAL_OK = True
except ImportError:
    _serial = None
    SERIAL_OK = False


# ── Enums / Dataclasses ─────────────────────────────────
class UPSStatus(Enum):
    ONLINE = "online"  # питание от сети
    ON_BATTERY = "on_battery"  # питание от батареи
    LOW_BATTERY = "low_battery"
    OVERLOAD = "overload"
    CHARGING = "charging"
    UNKNOWN = "unknown"
    OFFLINE = "offline"


class PowerAlert(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class UPSInfo:
    """Состояние ИБП."""

    name: str
    status: UPSStatus = UPSStatus.UNKNOWN
    battery_charge: float = -1.0  # %
    battery_runtime: float = -1.0  # секунды
    input_voltage: float = -1.0  # В
    output_voltage: float = -1.0  # В
    load_percent: float = -1.0  # %
    temperature: float = -1.0  # °C
    model: str = ""
    serial: str = ""
    last_update: float = 0.0


@dataclass
class PowerReading:
    """Показания датчика мощности."""

    sensor_id: str
    voltage: float = 0.0  # В
    current: float = 0.0  # А
    power: float = 0.0  # Вт
    energy_kwh: float = 0.0  # кВт·ч
    frequency: float = 0.0  # Гц
    ts: float = 0.0


# ── Power Sentry ─────────────────────────────────────────
class PowerSentry:
    """
    Мониторинг энергоснабжения и ИБП.

    Логика:
    1. Периодический опрос UPS через NUT/serial/SNMP
    2. Сбор показаний датчиков мощности (INA219/PZEM)
    3. Alerting при: battery < 20%, on_battery, overload
    4. Emergency shutdown path (с подтверждением)
    """

    MAX_HISTORY = 1000
    POLL_INTERVAL = 15  # сек

    def __init__(
        self,
        nut_host: str = "localhost",
        nut_port: int = 3493,
        alert_callback=None,
        data_path: str = "data/power_sentry.json",
    ):
        self._nut_host = nut_host
        self._nut_port = nut_port
        self._alert_callback = alert_callback
        self._data_path = data_path
        self._ups_list: Dict[str, UPSInfo] = {}
        self._sensors: Dict[str, PowerReading] = {}
        self._history: deque = deque(maxlen=self.MAX_HISTORY)
        self._alerts_log: deque = deque(maxlen=200)
        self._lock = threading.Lock()
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._emergency_armed = False

        # Пороги
        self._thresh_battery_warn = float(os.getenv("ARGOS_POWER_BATTERY_WARN", "30"))
        self._thresh_battery_crit = float(os.getenv("ARGOS_POWER_BATTERY_CRIT", "15"))
        self._thresh_load_warn = float(os.getenv("ARGOS_POWER_LOAD_WARN", "80"))
        self._thresh_voltage_low = float(os.getenv("ARGOS_POWER_VOLTAGE_LOW", "190"))
        self._thresh_voltage_high = float(os.getenv("ARGOS_POWER_VOLTAGE_HIGH", "250"))

        self._load_state()
        log.info("PowerSentry: init (%d UPS, %d sensors)", len(self._ups_list), len(self._sensors))

    # ── Persistence ──────────────────────────────────────
    def _load_state(self):
        try:
            if os.path.exists(self._data_path):
                with open(self._data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for u in data.get("ups_list", []):
                    ups = UPSInfo(
                        name=u["name"],
                        status=UPSStatus(u.get("status", "unknown")),
                        battery_charge=u.get("battery_charge", -1),
                        battery_runtime=u.get("battery_runtime", -1),
                        input_voltage=u.get("input_voltage", -1),
                        output_voltage=u.get("output_voltage", -1),
                        load_percent=u.get("load_percent", -1),
                        temperature=u.get("temperature", -1),
                        model=u.get("model", ""),
                        serial=u.get("serial", ""),
                    )
                    self._ups_list[ups.name] = ups
        except Exception as e:
            log.warning("PowerSentry load: %s", e)

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self._data_path) or ".", exist_ok=True)
            data = {
                "ups_list": [asdict(u) for u in self._ups_list.values()],
                "saved_at": time.time(),
            }
            for u in data["ups_list"]:
                u["status"] = u["status"] if isinstance(u["status"], str) else u["status"]
            with open(self._data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.debug("PowerSentry save: %s", e)

    # ── Start / Stop ─────────────────────────────────────
    def start(self) -> str:
        if self._running:
            return "⚡ Power Sentry: уже запущен."
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True, name="power-sentry")
        self._poll_thread.start()
        log.info("PowerSentry: запущен")
        return "⚡ Power Sentry: мониторинг запущен."

    def stop(self):
        self._running = False
        self._save_state()
        log.info("PowerSentry: остановлен")

    def _poll_loop(self):
        while self._running:
            try:
                self._poll_nut()
                self._check_thresholds()
                self._save_state()
            except Exception as e:
                log.debug("PowerSentry poll: %s", e)
            time.sleep(self.POLL_INTERVAL)

    # ── NUT Integration ──────────────────────────────────
    def _poll_nut(self):
        """Опрос NUT (Network UPS Tools)."""
        try:
            ups_names = self._nut_list_ups()
            for name in ups_names:
                info = self._nut_get_vars(name)
                if info:
                    with self._lock:
                        self._ups_list[name] = info
                    self._history.append(
                        {
                            "ts": time.time(),
                            "ups": name,
                            "charge": info.battery_charge,
                            "runtime": info.battery_runtime,
                            "voltage": info.input_voltage,
                            "load": info.load_percent,
                            "status": info.status.value,
                        }
                    )
        except Exception as e:
            # Fallback: попробовать upsc CLI
            self._poll_upsc_cli()

    def _nut_list_ups(self) -> List[str]:
        """Получить список UPS через NUT socket."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self._nut_host, self._nut_port))
            sock.send(b"LIST UPS\n")
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"END LIST UPS" in data:
                    break
            sock.close()
            names = []
            for line in data.decode("utf-8", errors="replace").splitlines():
                if line.startswith("UPS "):
                    parts = line.split('"')
                    name = line.split()[1] if len(line.split()) > 1 else ""
                    if name:
                        names.append(name)
            return names
        except Exception:
            return []

    def _nut_get_vars(self, ups_name: str) -> Optional[UPSInfo]:
        """Получить переменные UPS через NUT socket."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self._nut_host, self._nut_port))
            sock.send(f"LIST VAR {ups_name}\n".encode())
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"END LIST VAR" in data:
                    break
            sock.close()

            varz = {}
            for line in data.decode("utf-8", errors="replace").splitlines():
                if line.startswith("VAR "):
                    match = re.match(r'VAR \S+ (\S+) "(.+)"', line)
                    if match:
                        varz[match.group(1)] = match.group(2)

            status_map = {
                "OL": UPSStatus.ONLINE,
                "OB": UPSStatus.ON_BATTERY,
                "LB": UPSStatus.LOW_BATTERY,
                "OL CHRG": UPSStatus.CHARGING,
                "OVER": UPSStatus.OVERLOAD,
            }
            raw_status = varz.get("ups.status", "")
            ups_status = status_map.get(raw_status, UPSStatus.UNKNOWN)

            return UPSInfo(
                name=ups_name,
                status=ups_status,
                battery_charge=float(varz.get("battery.charge", -1)),
                battery_runtime=float(varz.get("battery.runtime", -1)),
                input_voltage=float(varz.get("input.voltage", -1)),
                output_voltage=float(varz.get("output.voltage", -1)),
                load_percent=float(varz.get("ups.load", -1)),
                temperature=float(varz.get("ups.temperature", -1)),
                model=varz.get("ups.model", ""),
                serial=varz.get("ups.serial", ""),
                last_update=time.time(),
            )
        except Exception:
            return None

    def _poll_upsc_cli(self):
        """Fallback: опрос через upsc CLI."""
        try:
            result = subprocess.run(["upsc", "-l"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return
            for name in result.stdout.strip().splitlines():
                name = name.strip()
                if not name:
                    continue
                res2 = subprocess.run(["upsc", name], capture_output=True, text=True, timeout=10)
                if res2.returncode != 0:
                    continue
                varz = {}
                for line in res2.stdout.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        varz[k.strip()] = v.strip()

                status_map = {
                    "OL": UPSStatus.ONLINE,
                    "OB": UPSStatus.ON_BATTERY,
                    "LB": UPSStatus.LOW_BATTERY,
                    "OL CHRG": UPSStatus.CHARGING,
                }
                raw = varz.get("ups.status", "")
                ups_status = status_map.get(raw, UPSStatus.UNKNOWN)

                info = UPSInfo(
                    name=name,
                    status=ups_status,
                    battery_charge=float(varz.get("battery.charge", -1)),
                    battery_runtime=float(varz.get("battery.runtime", -1)),
                    input_voltage=float(varz.get("input.voltage", -1)),
                    output_voltage=float(varz.get("output.voltage", -1)),
                    load_percent=float(varz.get("ups.load", -1)),
                    temperature=float(varz.get("ups.temperature", -1)),
                    model=varz.get("ups.model", ""),
                    serial=varz.get("ups.serial", ""),
                    last_update=time.time(),
                )
                with self._lock:
                    self._ups_list[name] = info
        except FileNotFoundError:
            pass
        except Exception as e:
            log.debug("upsc cli: %s", e)

    # ── Sensor reading (serial PZEM / INA219) ────────────
    def read_sensor(self, port: str = "/dev/ttyUSB0", sensor_id: str = "pzem_1") -> Optional[PowerReading]:
        """Чтение датчика мощности через serial (PZEM-004T протокол)."""
        if not SERIAL_OK:
            log.warning("PowerSentry: pyserial не установлен")
            return None
        try:
            ser = _serial.Serial(port, 9600, timeout=2)
            # PZEM-004T: модбас RTU, адрес 0x01, функция 0x04, регистр 0x0000, кол-во 10
            request = bytes([0x01, 0x04, 0x00, 0x00, 0x00, 0x0A, 0x70, 0x0D])
            ser.write(request)
            time.sleep(0.5)
            resp = ser.read(25)
            ser.close()
            if len(resp) >= 25:
                voltage = (resp[3] << 8 | resp[4]) / 10.0
                current = ((resp[5] << 8 | resp[6]) | ((resp[7] << 8 | resp[8]) << 16)) / 1000.0
                power = ((resp[9] << 8 | resp[10]) | ((resp[11] << 8 | resp[12]) << 16)) / 10.0
                energy = (resp[13] << 8 | resp[14]) | ((resp[15] << 8 | resp[16]) << 16)
                frequency = (resp[17] << 8 | resp[18]) / 10.0
                reading = PowerReading(
                    sensor_id=sensor_id,
                    voltage=voltage,
                    current=current,
                    power=power,
                    energy_kwh=energy / 1000.0,
                    frequency=frequency,
                    ts=time.time(),
                )
                with self._lock:
                    self._sensors[sensor_id] = reading
                return reading
        except Exception as e:
            log.debug("PowerSentry sensor read: %s", e)
        return None

    # ── Threshold checks ─────────────────────────────────
    def _check_thresholds(self):
        with self._lock:
            for ups in self._ups_list.values():
                # Battery low
                if 0 <= ups.battery_charge < self._thresh_battery_crit:
                    self._emit_alert(
                        PowerAlert.CRITICAL, f"⚡ UPS '{ups.name}': батарея КРИТИЧЕСКИ низкая ({ups.battery_charge}%)"
                    )
                elif 0 <= ups.battery_charge < self._thresh_battery_warn:
                    self._emit_alert(PowerAlert.WARNING, f"⚡ UPS '{ups.name}': батарея {ups.battery_charge}%")
                # On battery
                if ups.status == UPSStatus.ON_BATTERY:
                    self._emit_alert(
                        PowerAlert.WARNING,
                        f"⚡ UPS '{ups.name}': работает от БАТАРЕИ" f" (runtime: {ups.battery_runtime:.0f}s)",
                    )
                # Overload
                if ups.load_percent > self._thresh_load_warn:
                    self._emit_alert(PowerAlert.WARNING, f"⚡ UPS '{ups.name}': нагрузка {ups.load_percent}%")
                # Voltage anomaly
                if ups.input_voltage > 0:
                    if ups.input_voltage < self._thresh_voltage_low:
                        self._emit_alert(
                            PowerAlert.WARNING, f"⚡ UPS '{ups.name}': напряжение НИЗКОЕ ({ups.input_voltage}V)"
                        )
                    elif ups.input_voltage > self._thresh_voltage_high:
                        self._emit_alert(
                            PowerAlert.WARNING, f"⚡ UPS '{ups.name}': напряжение ВЫСОКОЕ ({ups.input_voltage}V)"
                        )

    def _emit_alert(self, level: PowerAlert, message: str):
        entry = {"ts": time.time(), "level": level.value, "message": message}
        self._alerts_log.append(entry)
        log.warning("PowerAlert [%s]: %s", level.value, message)
        if self._alert_callback:
            try:
                self._alert_callback(message)
            except Exception:
                pass

    # ── Emergency shutdown ───────────────────────────────
    def arm_emergency(self) -> str:
        """Поставить на «готовность» аварийное отключение."""
        self._emergency_armed = True
        self._log_event("emergency_armed")
        return "⚠ Emergency shutdown ARMED. Подтвердите: `power emergency confirm`"

    def execute_emergency(self, confirm: bool = False) -> str:
        """Аварийное отключение нагрузок через NUT."""
        if not self._emergency_armed:
            return "❌ Сначала: `power emergency arm`"
        if not confirm:
            return "❌ Нужно подтверждение: `power emergency confirm`"

        self._emergency_armed = False
        results = []

        # Попытка instcmd через NUT
        for ups_name in list(self._ups_list.keys()):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((self._nut_host, self._nut_port))
                cmd = f"INSTCMD {ups_name} shutdown.return\n"
                sock.send(cmd.encode())
                resp = sock.recv(1024).decode("utf-8", errors="replace")
                sock.close()
                results.append(f"  {ups_name}: {resp.strip()}")
            except Exception as e:
                results.append(f"  {ups_name}: ошибка — {e}")

        self._emit_alert(PowerAlert.EMERGENCY, "EMERGENCY SHUTDOWN выполнен")
        return "🔴 EMERGENCY SHUTDOWN:\n" + "\n".join(results) if results else "🔴 No UPS to shutdown."

    # ── Query ────────────────────────────────────────────
    def list_ups(self) -> List[dict]:
        with self._lock:
            return [asdict(u) for u in self._ups_list.values()]

    def get_ups(self, name: str) -> Optional[dict]:
        with self._lock:
            u = self._ups_list.get(name)
            return asdict(u) if u else None

    def get_readings(self) -> List[dict]:
        with self._lock:
            return [asdict(r) for r in self._sensors.values()]

    def get_history(self, limit: int = 50) -> List[dict]:
        return list(self._history)[-limit:]

    def get_alerts(self, limit: int = 20) -> List[dict]:
        return list(self._alerts_log)[-limit:]

    # ── Status ───────────────────────────────────────────
    def get_status(self) -> dict:
        with self._lock:
            ups_count = len(self._ups_list)
            on_battery = sum(1 for u in self._ups_list.values() if u.status == UPSStatus.ON_BATTERY)
            avg_charge = -1.0
            charges = [u.battery_charge for u in self._ups_list.values() if u.battery_charge >= 0]
            if charges:
                avg_charge = sum(charges) / len(charges)
        return {
            "running": self._running,
            "nut": f"{self._nut_host}:{self._nut_port}",
            "ups_count": ups_count,
            "on_battery": on_battery,
            "avg_charge": round(avg_charge, 1),
            "sensors": len(self._sensors),
            "emergency_armed": self._emergency_armed,
            "alerts": len(self._alerts_log),
            "history_points": len(self._history),
        }

    def status(self) -> str:
        s = self.get_status()
        lines = [
            "⚡ POWER SENTRY:",
            f"  Мониторинг: {'🟢 запущен' if s['running'] else '⚪ остановлен'}",
            f"  NUT: {s['nut']}",
            f"  UPS: {s['ups_count']} (на батарее: {s['on_battery']})",
        ]
        if s["avg_charge"] >= 0:
            lines.append(f"  Средний заряд: {s['avg_charge']}%")
        lines.append(f"  Датчики мощности: {s['sensors']}")
        if s["emergency_armed"]:
            lines.append("  ⚠ EMERGENCY ARMED")
        lines.append(f"  Алерты: {s['alerts']} | История: {s['history_points']}")

        # Per-UPS detail
        with self._lock:
            for ups in self._ups_list.values():
                lines.append(
                    f"\n  📦 {ups.name}: {ups.status.value}"
                    f" | charge={ups.battery_charge}%"
                    f" | load={ups.load_percent}%"
                    f" | Vin={ups.input_voltage}V"
                )
        return "\n".join(lines)

    def _log_event(self, event_type: str):
        log.info("PowerSentry [%s]", event_type)

    def shutdown(self):
        self.stop()


# ── Singleton ────────────────────────────────────────────
_instance: Optional[PowerSentry] = None


def get_power_sentry(**kwargs) -> PowerSentry:
    global _instance
    if _instance is None:
        _instance = PowerSentry(**kwargs)
    return _instance
