"""p2p_bridge.py — P2P сеть нод Аргоса с интеграцией команд"""
from __future__ import annotations
import os, socket, threading, json, time, hashlib
from src.argos_logger import get_logger
log = get_logger("argos.p2p")

class ArgosP2PBridge:
    DISCOVERY_PORT = int(os.getenv("ARGOS_P2P_PORT","55771"))
    SECRET = os.getenv("ARGOS_NETWORK_SECRET","argos_p2p_secret")

    def __init__(self, core=None):
        self.core = core
        self.node_id = os.getenv("ARGOS_NODE_ID", f"node_{socket.gethostname()}")
        self._nodes: dict[str,dict] = {}
        self._running = False
        self._threads: list[threading.Thread] = []

    def start(self) -> str:
        self._running = True
        t1 = threading.Thread(target=self._broadcast_loop, daemon=True)
        t2 = threading.Thread(target=self._listen_loop, daemon=True)
        self._threads = [t1, t2]
        for t in self._threads: t.start()
        log.info("P2P: запущен (порт %d)", self.DISCOVERY_PORT)
        return f"🌐 P2P сеть запущена. Нода: {self.node_id}"

    def broadcast_command(self, cmd: str, payload: dict = None):
        """Отправить команду всем узлам сети"""
        msg = json.dumps({"node_id": self.node_id, "cmd": cmd, "data": payload, "secret": self.SECRET[:8]})
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(msg.encode(), ("<broadcast>", self.DISCOVERY_PORT))

    def _broadcast_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self._running:
            try:
                msg = json.dumps({"node_id":self.node_id, "type": "heartbeat", "ts":time.time(),
                                  "secret":self.SECRET[:8]}).encode()
                sock.sendto(msg, ("<broadcast>", self.DISCOVERY_PORT))
            except Exception: pass
            time.sleep(10)

    def _listen_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("",self.DISCOVERY_PORT))
        while self._running:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data)
                if msg.get("secret") != self.SECRET[:8]: continue
                
                nid = msg.get("node_id")
                if nid == self.node_id: continue

                if msg.get("type") == "heartbeat":
                    self._nodes[nid] = {"addr":addr[0], "ts":time.time()}
                elif "cmd" in msg and self.core:
                    log.info("P2P: Получена команда [%s] от %s", msg['cmd'], nid)
                    self.core.process(msg['cmd'])
            except Exception: pass

    def network_status(self) -> str:
        active = {k:v for k,v in self._nodes.items() if time.time()-v["ts"]<60}
        return f"🌐 P2P: {len(active)} peers online."