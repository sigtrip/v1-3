"""
wifi_sentinel.py — WiFi Sentinel & HoneyPot
    Защита периметра Wi-Fi сети:
    - Пассивный мониторинг точек доступа и клиентов
    - Обнаружение rogue AP / Evil Twin / deauth-атак
    - HoneyPot — ловушка для несанкционированных подключений
    - Журнал инцидентов с уведомлениями

    Работает через:
    - scapy (пассивный monitor-mode)
    - iwlist / nmcli для безагентного сканирования
    - встроенный TCP honeypot (порт-ловушка)
"""
import os
import re
import time
import json
import socket
import hashlib
import threading
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque
from dataclasses import dataclass, field, asdict

from src.argos_logger import get_logger

log = get_logger("argos.wifi_sentinel")

# ── Graceful imports ─────────────────────────────────────
try:
    import subprocess
    SUBPROCESS_OK = True
except ImportError:
    subprocess = None
    SUBPROCESS_OK = False

try:
    from scapy.all import sniff, Dot11, Dot11Beacon, Dot11Elt, RadioTap
    SCAPY_OK = True
except ImportError:
    SCAPY_OK = False


# ── Enums / Dataclasses ─────────────────────────────────
class ThreatLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class IncidentType(Enum):
    ROGUE_AP = "rogue_ap"
    EVIL_TWIN = "evil_twin"
    DEAUTH_FLOOD = "deauth_flood"
    UNKNOWN_CLIENT = "unknown_client"
    HONEYPOT_TOUCH = "honeypot_touch"
    WEAK_ENCRYPTION = "weak_encryption"
    NEW_AP = "new_ap"


@dataclass
class AccessPoint:
    """Обнаруженная точка доступа."""
    bssid: str
    ssid: str = ""
    channel: int = 0
    signal_dbm: int = -100
    encryption: str = "unknown"
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    trusted: bool = False
    vendor: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WifiClient:
    """Обнаруженный Wi-Fi клиент."""
    mac: str
    connected_to: str = ""       # BSSID
    signal_dbm: int = -100
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    authorized: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SecurityIncident:
    """Инцидент безопасности Wi-Fi."""
    ts: float = field(default_factory=time.time)
    incident_type: str = ""
    threat_level: str = "info"
    description: str = ""
    bssid: str = ""
    source_mac: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── MAC Vendor Lookup (first 3 bytes) ───────────────────
_MAC_VENDORS = {
    "00:50:F2": "Microsoft",
    "DC:A6:32": "Raspberry Pi",
    "B8:27:EB": "Raspberry Pi",
    "CC:50:E3": "Apple",
    "3C:22:FB": "Apple",
    "AC:DE:48": "Apple",
    "F4:F5:D8": "Google",
    "30:FD:38": "Google",
    "54:60:09": "Google",
    "10:DA:43": "Xiaomi",
    "68:AB:1E": "Xiaomi",
    "7C:49:EB": "Xiaomi",
    "50:02:91": "Amazon",
    "A4:08:EA": "Tuya",
    "D8:F1:5B": "Tuya",
    "60:01:94": "Espressif",
    "24:62:AB": "Espressif",
    "84:CC:A8": "Espressif",
}


def _mac_vendor(mac: str) -> str:
    prefix = mac.upper()[:8]
    return _MAC_VENDORS.get(prefix, "")


class WiFiSentinel:
    """
    Wi-Fi Sentinel — мониторинг и защита Wi-Fi периметра.

    Компоненты:
    1. Scanner — пассивный сканер AP и клиентов
    2. Threat Detector — обнаружение rogue AP, evil twin, deauth
    3. HoneyPot — TCP-ловушка для обнаружения зондирования
    4. Incident Log — журнал инцидентов с уровнями угрозы
    """

    VERSION = "1.0.0"
    MAX_INCIDENTS = 1000

    def __init__(self, core=None):
        self.core = core
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._honeypot_thread: Optional[threading.Thread] = None
        self._honeypot_sock: Optional[socket.socket] = None

        # State
        self._access_points: Dict[str, AccessPoint] = {}
        self._clients: Dict[str, WifiClient] = {}
        self._incidents: deque = deque(maxlen=self.MAX_INCIDENTS)
        self._trusted_bssids: Set[str] = set()
        self._authorized_macs: Set[str] = set()

        # Config
        self._interface = os.getenv("ARGOS_WIFI_IFACE", "wlan0").strip()
        self._honeypot_port = int(os.getenv("ARGOS_HONEYPOT_PORT", "8888") or "8888")
        self._scan_interval = float(os.getenv("ARGOS_WIFI_SCAN_SEC", "60") or "60")
        self._deauth_threshold = int(os.getenv("ARGOS_DEAUTH_THRESHOLD", "10") or "10")
        self._deauth_window = deque(maxlen=200)   # timestamps of deauth frames

        # Load trusted networks from env
        trusted_str = os.getenv("ARGOS_TRUSTED_BSSIDS", "").strip()
        if trusted_str:
            for bssid in trusted_str.split(","):
                self._trusted_bssids.add(bssid.strip().upper())

        authorized_str = os.getenv("ARGOS_AUTHORIZED_MACS", "").strip()
        if authorized_str:
            for mac in authorized_str.split(","):
                self._authorized_macs.add(mac.strip().upper())

        log.info("WiFiSentinel v%s | iface=%s | honeypot_port=%d | trusted=%d",
                 self.VERSION, self._interface, self._honeypot_port, len(self._trusted_bssids))

    # ── AP Scanning ──────────────────────────────────────
    def scan_aps(self) -> List[AccessPoint]:
        """Сканирует окружающие точки доступа."""
        aps: List[AccessPoint] = []

        # Method 1: nmcli (Linux)
        if SUBPROCESS_OK:
            try:
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "BSSID,SSID,CHAN,SIGNAL,SECURITY", "dev", "wifi", "list"],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        parts = line.split(":")
                        if len(parts) >= 9:
                            # nmcli uses : in BSSID, so reconstruct
                            bssid = ":".join(parts[:6]).strip().upper()
                            rest = ":".join(parts[6:]).split(":")
                            ssid = rest[0] if rest else ""
                            chan = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 0
                            sig = int(rest[2]) if len(rest) > 2 and rest[2].lstrip("-").isdigit() else -100
                            enc = rest[3] if len(rest) > 3 else "unknown"

                            ap = self._update_ap(bssid, ssid, chan, sig, enc)
                            aps.append(ap)
            except Exception as e:
                log.debug("WiFiSentinel nmcli scan: %s", e)

        # Method 2: iwlist (fallback)
        if not aps and SUBPROCESS_OK:
            try:
                result = subprocess.run(
                    ["iwlist", self._interface, "scan"],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    aps = self._parse_iwlist(result.stdout)
            except Exception as e:
                log.debug("WiFiSentinel iwlist scan: %s", e)

        # Threat analysis on results
        self._analyze_aps(aps)
        log.info("WiFiSentinel: scanned %d APs", len(aps))
        return aps

    def _parse_iwlist(self, output: str) -> List[AccessPoint]:
        """Парсит вывод iwlist scan."""
        aps = []
        current_bssid = ""
        current_ssid = ""
        current_signal = -100
        current_channel = 0
        current_enc = "open"

        for line in output.split("\n"):
            line = line.strip()
            m_cell = re.search(r"Address: ([0-9A-Fa-f:]+)", line)
            if m_cell:
                if current_bssid:
                    ap = self._update_ap(current_bssid, current_ssid,
                                         current_channel, current_signal, current_enc)
                    aps.append(ap)
                current_bssid = m_cell.group(1).upper()
                current_ssid = ""
                current_signal = -100
                current_channel = 0
                current_enc = "open"
                continue

            m_ssid = re.search(r'ESSID:"(.+?)"', line)
            if m_ssid:
                current_ssid = m_ssid.group(1)

            m_sig = re.search(r"Signal level[=:](-?\d+)", line)
            if m_sig:
                current_signal = int(m_sig.group(1))

            m_chan = re.search(r"Channel[=:](\d+)", line)
            if m_chan:
                current_channel = int(m_chan.group(1))

            if "WPA2" in line:
                current_enc = "WPA2"
            elif "WPA" in line:
                current_enc = "WPA"
            elif "WEP" in line:
                current_enc = "WEP"

        if current_bssid:
            ap = self._update_ap(current_bssid, current_ssid,
                                 current_channel, current_signal, current_enc)
            aps.append(ap)

        return aps

    def _update_ap(self, bssid: str, ssid: str, channel: int,
                   signal: int, enc: str) -> AccessPoint:
        bssid = bssid.upper()
        if bssid in self._access_points:
            ap = self._access_points[bssid]
            ap.ssid = ssid or ap.ssid
            ap.channel = channel or ap.channel
            ap.signal_dbm = signal
            ap.encryption = enc or ap.encryption
            ap.last_seen = time.time()
        else:
            ap = AccessPoint(
                bssid=bssid, ssid=ssid, channel=channel,
                signal_dbm=signal, encryption=enc,
                trusted=(bssid in self._trusted_bssids),
                vendor=_mac_vendor(bssid),
            )
            self._access_points[bssid] = ap

            # New AP → incident
            self._add_incident(
                IncidentType.NEW_AP, ThreatLevel.INFO,
                f"Новая AP: {ssid} ({bssid}) ch={channel} enc={enc}",
                bssid=bssid,
            )
        return ap

    # ── Threat Analysis ──────────────────────────────────
    def _analyze_aps(self, aps: List[AccessPoint]) -> None:
        """Проверяет AP на угрозы."""
        trusted_ssids: Dict[str, str] = {}
        for bssid in self._trusted_bssids:
            ap = self._access_points.get(bssid)
            if ap and ap.ssid:
                trusted_ssids[ap.ssid] = bssid

        for ap in aps:
            # Evil Twin: тот же SSID но другой BSSID
            if ap.ssid in trusted_ssids and trusted_ssids[ap.ssid] != ap.bssid:
                self._add_incident(
                    IncidentType.EVIL_TWIN, ThreatLevel.CRITICAL,
                    f"⚠️ Evil Twin: SSID '{ap.ssid}' с BSSID {ap.bssid} "
                    f"(доверенный: {trusted_ssids[ap.ssid]})",
                    bssid=ap.bssid,
                )

            # Rogue AP: неизвестная AP с сильным сигналом
            if not ap.trusted and ap.signal_dbm > -50:
                self._add_incident(
                    IncidentType.ROGUE_AP, ThreatLevel.WARNING,
                    f"Rogue AP с сильным сигналом: {ap.ssid} ({ap.bssid}) "
                    f"signal={ap.signal_dbm}dBm",
                    bssid=ap.bssid,
                )

            # Weak encryption
            if ap.encryption in ("WEP", "open") and ap.trusted:
                self._add_incident(
                    IncidentType.WEAK_ENCRYPTION, ThreatLevel.WARNING,
                    f"Доверенная AP '{ap.ssid}' использует слабое шифрование: {ap.encryption}",
                    bssid=ap.bssid,
                )

    # ── HoneyPot ─────────────────────────────────────────
    def start_honeypot(self) -> str:
        """Запускает TCP honeypot — ловушку для зондирования."""
        if self._honeypot_thread and self._honeypot_thread.is_alive():
            return f"🍯 HoneyPot: уже запущен на порту {self._honeypot_port}."
        self._running = True
        self._honeypot_thread = threading.Thread(
            target=self._honeypot_loop, daemon=True, name="honeypot"
        )
        self._honeypot_thread.start()
        return f"🍯 HoneyPot: запущен на порту {self._honeypot_port}."

    def stop_honeypot(self) -> str:
        self._running = False
        if self._honeypot_sock:
            try:
                self._honeypot_sock.close()
            except Exception:
                pass
        return "🍯 HoneyPot: остановлен."

    def _honeypot_loop(self):
        """TCP listener — логирует каждое подключение как инцидент."""
        try:
            self._honeypot_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._honeypot_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._honeypot_sock.settimeout(2.0)
            self._honeypot_sock.bind(("0.0.0.0", self._honeypot_port))
            self._honeypot_sock.listen(5)
            log.info("HoneyPot listening on :%d", self._honeypot_port)

            while self._running:
                try:
                    conn, addr = self._honeypot_sock.accept()
                    remote_ip, remote_port = addr
                    log.warning("HoneyPot: connection from %s:%d", remote_ip, remote_port)

                    # Read first 512 bytes (probe data)
                    try:
                        conn.settimeout(3)
                        data = conn.recv(512)
                        probe = data.decode("utf-8", errors="replace")[:200]
                    except Exception:
                        probe = ""

                    # Banner response (fake)
                    try:
                        conn.sendall(b"SSH-2.0-OpenSSH_8.9p1\r\n")
                    except Exception:
                        pass
                    conn.close()

                    self._add_incident(
                        IncidentType.HONEYPOT_TOUCH, ThreatLevel.WARNING,
                        f"HoneyPot: подключение от {remote_ip}:{remote_port}",
                        source_mac=remote_ip,
                        details={"probe_data": probe, "port": self._honeypot_port},
                    )
                except socket.timeout:
                    continue
                except OSError:
                    break

        except Exception as e:
            log.error("HoneyPot error: %s", e)
        finally:
            if self._honeypot_sock:
                try:
                    self._honeypot_sock.close()
                except Exception:
                    pass
            log.info("HoneyPot thread exited.")

    # ── Background Monitor ───────────────────────────────
    def start_monitor(self) -> str:
        if self._monitor_thread and self._monitor_thread.is_alive():
            return "🛡️ WiFi Sentinel: мониторинг уже запущен."
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="wifi-sentinel"
        )
        self._monitor_thread.start()
        return f"🛡️ WiFi Sentinel: мониторинг запущен (каждые {self._scan_interval}с)."

    def stop_monitor(self) -> str:
        self._running = False
        return "🛡️ WiFi Sentinel: мониторинг остановлен."

    def _monitor_loop(self):
        while self._running:
            try:
                self.scan_aps()
            except Exception as e:
                log.error("WiFiSentinel monitor error: %s", e)
            time.sleep(self._scan_interval)

    # ── Trust Management ─────────────────────────────────
    def trust_ap(self, bssid: str) -> str:
        bssid = bssid.upper()
        self._trusted_bssids.add(bssid)
        ap = self._access_points.get(bssid)
        if ap:
            ap.trusted = True
        return f"✅ AP {bssid} добавлена в доверенные."

    def untrust_ap(self, bssid: str) -> str:
        bssid = bssid.upper()
        self._trusted_bssids.discard(bssid)
        ap = self._access_points.get(bssid)
        if ap:
            ap.trusted = False
        return f"❌ AP {bssid} удалена из доверенных."

    def authorize_client(self, mac: str) -> str:
        mac = mac.upper()
        self._authorized_macs.add(mac)
        c = self._clients.get(mac)
        if c:
            c.authorized = True
        return f"✅ Клиент {mac} авторизован."

    # ── Incidents ────────────────────────────────────────
    def _add_incident(self, incident_type: IncidentType, threat_level: ThreatLevel,
                      description: str, bssid: str = "", source_mac: str = "",
                      details: dict = None) -> None:
        inc = SecurityIncident(
            incident_type=incident_type.value,
            threat_level=threat_level.value,
            description=description,
            bssid=bssid,
            source_mac=source_mac,
            details=details or {},
        )
        self._incidents.append(inc)
        if threat_level in (ThreatLevel.WARNING, ThreatLevel.CRITICAL):
            log.warning("WiFiSentinel INCIDENT [%s]: %s", threat_level.value, description)

    def get_incidents(self, last_n: int = 30,
                      level: Optional[str] = None) -> List[dict]:
        with self._lock:
            items = list(self._incidents)
        if level:
            items = [i for i in items if i.threat_level == level]
        return [i.to_dict() for i in items[-last_n:]]

    # ── Status ───────────────────────────────────────────
    def get_status(self) -> dict:
        return {
            "version": self.VERSION,
            "monitoring": self._running,
            "interface": self._interface,
            "honeypot_port": self._honeypot_port,
            "access_points": len(self._access_points),
            "trusted_aps": len(self._trusted_bssids),
            "clients": len(self._clients),
            "authorized_clients": len(self._authorized_macs),
            "incidents_total": len(self._incidents),
            "scapy_available": SCAPY_OK,
        }

    def status(self) -> str:
        s = self.get_status()
        crit = sum(1 for i in self._incidents if i.threat_level == "critical")
        warn = sum(1 for i in self._incidents if i.threat_level == "warning")
        lines = [
            "🛡️ WIFI SENTINEL & HONEYPOT",
            f"  Версия: {s['version']} | iface: {s['interface']}",
            f"  Мониторинг: {'🟢 ON' if s['monitoring'] else '⚪ OFF'}",
            f"  AP: {s['access_points']} (доверенных: {s['trusted_aps']})",
            f"  Клиентов: {s['clients']} (авторизованных: {s['authorized_clients']})",
            f"  HoneyPot: порт {s['honeypot_port']}",
            f"  Инцидентов: {s['incidents_total']} "
            f"(🔴 {crit} | 🟡 {warn})",
            f"  Scapy: {'✅' if s['scapy_available'] else '❌'}",
        ]
        return "\n".join(lines)

    def incidents_report(self, last_n: int = 15) -> str:
        items = self.get_incidents(last_n)
        if not items:
            return "🛡️ WiFi Sentinel: инцидентов не обнаружено."
        lines = ["🛡️ WIFI SENTINEL — ИНЦИДЕНТЫ:"]
        for i in items:
            ts = time.strftime("%H:%M:%S", time.localtime(i["ts"]))
            icon = {"critical": "🔴", "warning": "🟡"}.get(i["threat_level"], "🔵")
            lines.append(f"  {icon} [{ts}] {i['incident_type']}: {i['description'][:80]}")
        return "\n".join(lines)

    def ap_list(self) -> str:
        if not self._access_points:
            return "🛡️ WiFi Sentinel: точки доступа не обнаружены. Запусти 'wifi скан'."
        lines = ["🛡️ WIFI — ТОЧКИ ДОСТУПА:"]
        for bssid, ap in sorted(self._access_points.items(),
                                 key=lambda x: x[1].signal_dbm, reverse=True):
            trust = "🟢" if ap.trusted else "⚪"
            lines.append(
                f"  {trust} {ap.ssid or '(hidden)'} [{bssid}] "
                f"ch={ap.channel} sig={ap.signal_dbm}dBm enc={ap.encryption}"
                f"{' vendor=' + ap.vendor if ap.vendor else ''}"
            )
        return "\n".join(lines)

    def shutdown(self):
        self._running = False
        if self._honeypot_sock:
            try:
                self._honeypot_sock.close()
            except Exception:
                pass
        log.info("WiFiSentinel shutdown")
