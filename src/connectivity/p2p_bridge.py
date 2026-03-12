"""p2p_bridge.py — P2P сеть нод Аргоса"""
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

    def stop(self) -> str:
        self._running = False
        return "🌐 P2P остановлена."

    def _broadcast_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self._running:
            try:
                msg = json.dumps({"node_id":self.node_id,"ts":time.time(),
                                  "secret":self.SECRET[:8]}).encode()
                sock.sendto(msg, ("<broadcast>", self.DISCOVERY_PORT))
            except Exception: pass
            time.sleep(10)

    def _listen_loop(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("",self.DISCOVERY_PORT))
            sock.settimeout(5)
        except Exception as e:
            log.warning("P2P listen: %s", e); return
        while self._running:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data)
                nid = msg.get("node_id","")
                if nid and nid != self.node_id:
                    self._nodes[nid] = {"addr":addr[0],"ts":time.time()}
            except socket.timeout: pass
            except Exception: pass

    def network_status(self) -> str:
        active = {k:v for k,v in self._nodes.items() if time.time()-v["ts"]<60}
        lines = [f"🌐 P2P СЕТЬ\n  Нода: {self.node_id}\n  Активных нод: {len(active)+1}"]
        lines.append(f"  ● {self.node_id} (master, я)")
        for nid, info in active.items():
            lines.append(f"  ● {nid} ({info['addr']})")
        return "\n".join(lines)

    def sync_skills_from_network(self) -> str:
        if not self._nodes: return "🌐 Нет доступных нод для синхронизации."
        return f"🔄 Синхронизация с {len(self._nodes)} нодами... (в разработке)"
