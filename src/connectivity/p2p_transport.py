"""
p2p_transport.py — транспортный слой P2P (этап миграции на libp2p).
По умолчанию использует TCP JSON, а режим libp2p работает как совместимый fallback.
"""
import importlib.util
import json
import os
import socket
from src.argos_logger import get_logger

log = get_logger("argos.p2p.transport")


class P2PTransportClient:
    def __init__(self, port: int, mode: str | None = None):
        self.port = int(port)
        self.request_timeout = max(1, min(int(os.getenv("ARGOS_P2P_TIMEOUT_SEC", "8") or "8"), 60))
        self.strict = os.getenv("ARGOS_P2P_TRANSPORT_STRICT", "off").strip().lower() in {"1", "on", "true", "yes", "да"}
        raw_mode = (mode or os.getenv("ARGOS_P2P_TRANSPORT", "auto") or "auto").strip().lower()
        self.mode = self._resolve_mode(raw_mode)

    def _resolve_mode(self, requested: str) -> str:
        if requested not in {"auto", "tcp", "libp2p"}:
            requested = "auto"

        if requested == "tcp":
            return "tcp"

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
        return f"🛰️ P2P transport: requested={os.getenv('ARGOS_P2P_TRANSPORT', 'auto')} effective={self.mode} strict={'on' if self.strict else 'off'}"

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

        return self._tcp_request(addr, payload, t)

    def _libp2p_request(self, addr: str, payload: dict, timeout: int) -> dict:
        """
        Этап 1 миграции: интерфейс и совместимость.
        Пока протокол request/response делегируется в TCP transport.
        """
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
