"""
p2p_transport.py — транспортный слой P2P (этап миграции на libp2p).
По умолчанию использует TCP JSON, а режим libp2p работает как совместимый fallback.
Расширенные транспорты: WireGuard, ZeroTier (UDP-tunnel overlay).
ZKP-proof: подпись пакетов через ArgosZKPEngine (privacy-routing).
"""
import importlib.util
import json
import os
import socket
import struct
import subprocess
from typing import Tuple, Optional
from src.argos_logger import get_logger

log = get_logger("argos.p2p.transport")


# ═══════════════════════════════════════════════════════════
# БАЗОВЫЙ КЛАСС ТРАНСПОРТА
# ═══════════════════════════════════════════════════════════
class P2PTransportBase:
    """Абстрактный базовый класс для всех P2P-транспортов."""

    name: str = "base"

    def send(self, peer_id: str, payload: bytes) -> None:
        raise NotImplementedError

    def recv(self) -> Tuple[str, bytes]:
        raise NotImplementedError

    def request(self, addr: str, payload: dict, timeout: int = 8) -> dict:
        raise NotImplementedError

    def status(self) -> str:
        return f"🛰️ Transport[{self.name}]: not implemented"

    def is_available(self) -> bool:
        return False


# ═══════════════════════════════════════════════════════════
# TCP ТРАНСПОРТ (основной)
# ═══════════════════════════════════════════════════════════
class TCPTransport(P2PTransportBase):
    """Стандартный TCP JSON транспорт."""

    name = "tcp"

    def __init__(self, port: int = 55771):
        self.port = int(port)

    def request(self, addr: str, payload: dict, timeout: int = 8) -> dict:
        sock = socket.socket()
        try:
            sock.settimeout(timeout)
            sock.connect((addr, self.port))
            sock.sendall(json.dumps(payload).encode())
            raw = sock.recv(65536)
            data = json.loads((raw or b"{}").decode() or "{}")
            return data if isinstance(data, dict) else {"error": "invalid response"}
        finally:
            sock.close()

    def send(self, peer_id: str, payload: bytes) -> None:
        # peer_id = "ip:port"
        parts = peer_id.rsplit(":", 1)
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else self.port
        sock = socket.socket()
        try:
            sock.settimeout(5)
            sock.connect((host, port))
            sock.sendall(payload)
        finally:
            sock.close()

    def recv(self) -> Tuple[str, bytes]:
        raise NotImplementedError("TCP recv — используется через TCP server в bridge")

    def is_available(self) -> bool:
        return True

    def status(self) -> str:
        return f"🛰️ Transport[tcp]: port={self.port} ✓"


# ═══════════════════════════════════════════════════════════
# WIREGUARD ТРАНСПОРТ
# ═══════════════════════════════════════════════════════════
class WireGuardTransport(P2PTransportBase):
    """
    Транспорт поверх WireGuard — использует UDP-туннель.
    Требует настроенный WireGuard интерфейс (wg0).
    Передача осуществляется через TCP-over-WG (трафик инкапсулирован в WG-туннеле).
    """

    name = "wireguard"

    def __init__(self, wg_interface: str = "wg0", port: int = 55771):
        self.iface = wg_interface
        self.port = int(port)
        self._wg_ip: Optional[str] = None

    def _detect_wg_ip(self) -> Optional[str]:
        """Определяет IP-адрес WireGuard интерфейса."""
        if self._wg_ip:
            return self._wg_ip
        try:
            result = subprocess.run(
                ["ip", "-4", "addr", "show", self.iface],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return None
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("inet "):
                    ip_cidr = line.split()[1]
                    self._wg_ip = ip_cidr.split("/")[0]
                    return self._wg_ip
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def is_available(self) -> bool:
        """WireGuard доступен, если интерфейс поднят и имеет IP."""
        return self._detect_wg_ip() is not None

    def send(self, peer_id: str, payload: bytes) -> None:
        """Отправка через TCP-сокет на WireGuard IP пира."""
        parts = peer_id.rsplit(":", 1)
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else self.port
        sock = socket.socket()
        try:
            sock.settimeout(8)
            sock.connect((host, port))
            # Длина + данные (length-prefixed)
            sock.sendall(struct.pack("!I", len(payload)) + payload)
        finally:
            sock.close()

    def recv(self) -> Tuple[str, bytes]:
        raise NotImplementedError("WireGuard recv — используется через bridge listener")

    def request(self, addr: str, payload: dict, timeout: int = 8) -> dict:
        """JSON request через WireGuard туннель."""
        sock = socket.socket()
        try:
            sock.settimeout(timeout)
            sock.connect((addr, self.port))
            sock.sendall(json.dumps(payload).encode())
            raw = sock.recv(65536)
            data = json.loads((raw or b"{}").decode() or "{}")
            return data if isinstance(data, dict) else {"error": "invalid response"}
        finally:
            sock.close()

    def get_peers(self) -> list[dict]:
        """Получает список пиров WireGuard через wg show."""
        peers = []
        try:
            result = subprocess.run(
                ["wg", "show", self.iface, "dump"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return peers
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:  # Пропускаем заголовок
                parts = line.split("\t")
                if len(parts) >= 4:
                    peers.append({
                        "public_key": parts[0],
                        "endpoint": parts[2] if parts[2] != "(none)" else None,
                        "allowed_ips": parts[3],
                        "latest_handshake": int(parts[4]) if len(parts) > 4 else 0,
                        "transfer_rx": int(parts[5]) if len(parts) > 5 else 0,
                        "transfer_tx": int(parts[6]) if len(parts) > 6 else 0,
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return peers

    def status(self) -> str:
        wg_ip = self._detect_wg_ip()
        if not wg_ip:
            return f"🛰️ Transport[wireguard]: интерфейс {self.iface} не найден ✗"
        peers = self.get_peers()
        return f"🛰️ Transport[wireguard]: {self.iface}={wg_ip} peers={len(peers)} ✓"


# ═══════════════════════════════════════════════════════════
# ZEROTIER ТРАНСПОРТ
# ═══════════════════════════════════════════════════════════
class ZeroTierTransport(P2PTransportBase):
    """
    Транспорт поверх ZeroTier — виртуальная L2-сеть.
    Требует установленный zerotier-cli и подключённую сеть.
    """

    name = "zerotier"

    def __init__(self, network_id: str = "", port: int = 55771):
        self.network_id = network_id or os.getenv("ARGOS_ZT_NETWORK", "")
        self.port = int(port)
        self._zt_ip: Optional[str] = None

    def _detect_zt_ip(self) -> Optional[str]:
        """Определяет IP-адрес ZeroTier через zerotier-cli."""
        if self._zt_ip:
            return self._zt_ip
        try:
            result = subprocess.run(
                ["zerotier-cli", "listnetworks", "-j"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return None
            networks = json.loads(result.stdout or "[]")
            for net in networks:
                if self.network_id and net.get("nwid") != self.network_id:
                    continue
                addrs = net.get("assignedAddresses", [])
                for addr in addrs:
                    ip = addr.split("/")[0]
                    if "." in ip:  # IPv4
                        self._zt_ip = ip
                        return self._zt_ip
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        return None

    def is_available(self) -> bool:
        return self._detect_zt_ip() is not None

    def send(self, peer_id: str, payload: bytes) -> None:
        parts = peer_id.rsplit(":", 1)
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else self.port
        sock = socket.socket()
        try:
            sock.settimeout(8)
            sock.connect((host, port))
            sock.sendall(struct.pack("!I", len(payload)) + payload)
        finally:
            sock.close()

    def recv(self) -> Tuple[str, bytes]:
        raise NotImplementedError("ZeroTier recv — используется через bridge listener")

    def request(self, addr: str, payload: dict, timeout: int = 8) -> dict:
        sock = socket.socket()
        try:
            sock.settimeout(timeout)
            sock.connect((addr, self.port))
            sock.sendall(json.dumps(payload).encode())
            raw = sock.recv(65536)
            data = json.loads((raw or b"{}").decode() or "{}")
            return data if isinstance(data, dict) else {"error": "invalid response"}
        finally:
            sock.close()

    def get_peers(self) -> list[dict]:
        """Список пиров ZeroTier."""
        try:
            result = subprocess.run(
                ["zerotier-cli", "listpeers", "-j"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return []
            return json.loads(result.stdout or "[]")
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return []

    def status(self) -> str:
        zt_ip = self._detect_zt_ip()
        if not zt_ip:
            return f"🛰️ Transport[zerotier]: не подключён ✗"
        peers = self.get_peers()
        nw = f" nw={self.network_id[:10]}" if self.network_id else ""
        return f"🛰️ Transport[zerotier]: ip={zt_ip}{nw} peers={len(peers)} ✓"


# ═══════════════════════════════════════════════════════════
# РЕЕСТР ТРАНСПОРТОВ
# ═══════════════════════════════════════════════════════════
class TransportRegistry:
    """
    Реестр всех доступных транспортов.
    Позволяет регистрировать, удалять и выбирать транспорт по имени/весу.
    """

    def __init__(self):
        self._transports: dict[str, P2PTransportBase] = {}
        self._weights: dict[str, float] = {}

    def register(self, name: str, transport: P2PTransportBase, weight: float = 1.0):
        """Регистрирует транспорт с указанным весом (0.0-2.0)."""
        self._transports[name] = transport
        self._weights[name] = max(0.0, min(float(weight), 2.0))
        log.info("Transport registered: %s (weight=%.2f)", name, self._weights[name])

    def unregister(self, name: str) -> bool:
        if name in self._transports:
            del self._transports[name]
            self._weights.pop(name, None)
            return True
        return False

    def get(self, name: str) -> Optional[P2PTransportBase]:
        return self._transports.get(name)

    def set_weight(self, name: str, weight: float) -> bool:
        if name not in self._transports:
            return False
        self._weights[name] = max(0.0, min(float(weight), 2.0))
        return True

    def best(self) -> Optional[P2PTransportBase]:
        """Возвращает транспорт с наибольшим весом среди доступных."""
        available = [
            (name, t) for name, t in self._transports.items()
            if t.is_available() and self._weights.get(name, 0) > 0
        ]
        if not available:
            return None
        best_name = max(available, key=lambda x: self._weights.get(x[0], 0))[0]
        return self._transports[best_name]

    def all_available(self) -> list[tuple[str, P2PTransportBase]]:
        return [
            (name, t) for name, t in self._transports.items()
            if t.is_available()
        ]

    def status(self) -> str:
        lines = ["📡 TRANSPORT REGISTRY:"]
        for name, transport in self._transports.items():
            w = self._weights.get(name, 1.0)
            avail = "✓" if transport.is_available() else "✗"
            lines.append(f"  {name}: weight={w:.2f} {avail}")
        if not self._transports:
            lines.append("  (пусто)")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# ZKP-ОБЁРТКА ДЛЯ ТРАНСПОРТОВ (privacy-routing)
# ═══════════════════════════════════════════════════════════
class ZKPTransportWrapper(P2PTransportBase):
    """
    Обёртка: подписывает исходящие пакеты ZKP-proof.
    При приёме — верифицирует proof перед обработкой.
    Делегирует реальную отправку/приём внутреннему транспорту.
    """

    name = "zkp-wrapped"

    def __init__(self, inner: P2PTransportBase, zkp_engine=None):
        self.inner = inner
        self.zkp = zkp_engine  # ArgosZKPEngine из src/security/zkp.py
        self.name = f"zkp+{inner.name}"

    def is_available(self) -> bool:
        return self.inner.is_available()

    def request(self, addr: str, payload: dict, timeout: int = 8) -> dict:
        """Подписывает запрос ZKP-proof если engine активен."""
        if self.zkp and self.zkp.enabled:
            import uuid as _uuid
            req_id = payload.get("request_id", str(_uuid.uuid4()))
            action = payload.get("action", "request")
            challenge = self.zkp.challenge(action, req_id)
            proof = self.zkp.sign(challenge)
            payload = {**payload, "zkp_proof": proof, "zkp_challenge": challenge}
        return self.inner.request(addr, payload, timeout)

    def send(self, peer_id: str, payload: bytes) -> None:
        """Подписывает payload ZKP-proof при отправке."""
        if self.zkp and self.zkp.enabled:
            from hashlib import sha256
            proof_bytes = sha256(payload + self.zkp.node_id.encode()).digest()
            payload = proof_bytes + payload
        self.inner.send(peer_id, payload)

    def recv(self) -> Tuple[str, bytes]:
        return self.inner.recv()

    def verify_incoming(self, data: dict) -> bool:
        """Верифицирует ZKP-proof во входящем пакете."""
        if not self.zkp or not self.zkp.enabled:
            return True  # ZKP отключён — пропускаем
        proof = data.get("zkp_proof")
        challenge = data.get("zkp_challenge")
        if not proof or not challenge:
            return False
        return self.zkp.verify(proof, challenge)

    def status(self) -> str:
        zkp_state = "ON" if (self.zkp and self.zkp.enabled) else "OFF"
        return f"🛡️ Transport[{self.name}]: zkp={zkp_state} inner={self.inner.status()}"


# ═══════════════════════════════════════════════════════════
# ОСНОВНОЙ КЛИЕНТ (обратная совместимость)
# ═══════════════════════════════════════════════════════════
class P2PTransportClient:
    def __init__(self, port: int, mode: str | None = None):
        self.port = int(port)
        self.request_timeout = max(1, min(int(os.getenv("ARGOS_P2P_TIMEOUT_SEC", "8") or "8"), 60))
        self.strict = os.getenv("ARGOS_P2P_TRANSPORT_STRICT", "off").strip().lower() in {"1", "on", "true", "yes", "да"}
        raw_mode = (mode or os.getenv("ARGOS_P2P_TRANSPORT", "auto") or "auto").strip().lower()
        self.mode = self._resolve_mode(raw_mode)

        # Реестр транспортов
        self.registry = TransportRegistry()
        self._init_transports()

    def _init_transports(self):
        """Инициализация всех встроенных транспортов."""
        # TCP — всегда доступен
        self.registry.register("tcp", TCPTransport(self.port), weight=0.8)

        # WireGuard — если включён в env
        wg_iface = os.getenv("ARGOS_WG_INTERFACE", "").strip()
        if wg_iface:
            wg = WireGuardTransport(wg_interface=wg_iface, port=self.port)
            self.registry.register("wireguard", wg, weight=1.2)

        # ZeroTier — если включён в env
        zt_net = os.getenv("ARGOS_ZT_NETWORK", "").strip()
        if zt_net:
            zt = ZeroTierTransport(network_id=zt_net, port=self.port)
            self.registry.register("zerotier", zt, weight=1.1)

    def register_transport(self, name: str, transport: P2PTransportBase, weight: float = 1.0):
        """Публичный API для регистрации custom-транспортов."""
        self.registry.register(name, transport, weight)

    def _resolve_mode(self, requested: str) -> str:
        if requested not in {"auto", "tcp", "libp2p", "wireguard", "zerotier"}:
            requested = "auto"

        if requested == "tcp":
            return "tcp"

        if requested in ("wireguard", "zerotier"):
            return requested

        libp2p_available = importlib.util.find_spec("libp2p") is not None
        if requested == "libp2p":
            if libp2p_available:
                return "libp2p"
            if self.strict:
                return "disabled"
            log.warning("libp2p не найден, fallback на tcp")
            return "tcp"

        if libp2p_available:
            return "libp2p"
        return "tcp"

    def status(self) -> str:
        lines = [
            f"🛰️ P2P transport: requested={os.getenv('ARGOS_P2P_TRANSPORT', 'auto')} "
            f"effective={self.mode} strict={'on' if self.strict else 'off'}",
        ]
        for name, t in self.registry.all_available():
            lines.append(f"  ✓ {name}: {t.status()}")
        return "\n".join(lines)

    def request(self, addr: str, payload: dict, timeout: int | None = None) -> dict:
        t = timeout or self.request_timeout
        if self.mode == "disabled":
            raise RuntimeError("libp2p strict mode enabled, но пакет libp2p недоступен")

        if self.mode == "libp2p":
            try:
                return self._libp2p_request(addr, payload, t)
            except Exception as e:
                if self.strict:
                    raise
                log.warning("libp2p request fallback на tcp: %s", e)
                return self._tcp_request(addr, payload, t)

        # Попробовать лучший транспорт из реестра
        best = self.registry.best()
        if best and best.name != "tcp":
            try:
                return best.request(addr, payload, t)
            except Exception as e:
                log.warning("%s request fallback на tcp: %s", best.name, e)

        return self._tcp_request(addr, payload, t)

    def _libp2p_request(self, addr: str, payload: dict, timeout: int) -> dict:
        return self._tcp_request(addr, payload, timeout)

    def _tcp_request(self, addr: str, payload: dict, timeout: int) -> dict:
        sock = socket.socket()
        try:
            sock.settimeout(timeout)
            sock.connect((addr, self.port))
            sock.sendall(json.dumps(payload).encode())
            raw = sock.recv(65536)
            data = json.loads((raw or b"{}").decode() or "{}")
            return data if isinstance(data, dict) else {"error": "invalid response"}
        finally:
            sock.close()


# README aliases
P2PTransport = P2PTransportClient
