"""
p2p_bridge.py — P2P Сеть Аргоса
  Ноды находят друг друга в локальной сети и интернете.
  Объединяют вычислительную мощь, обмениваются навыками.
  Задачи распределяются по мощности и возрасту ноды.
"""
import os
import json
import socket
import threading
import time
import uuid
import hashlib
import platform
import psutil
import datetime
import requests
from collections import deque
from types import SimpleNamespace
from typing import Optional

try:
    from src.observability import get_acceptance_snapshot
except Exception:  # pragma: no cover
    def get_acceptance_snapshot(window: int = 120) -> dict:
        return {"rate": 1.0, "samples": 0, "accepted": 0, "rejected": 0}

# ── КОНСТАНТЫ ─────────────────────────────────────────────
P2P_PORT        = 55771          # Порт для P2P связи
BROADCAST_PORT  = 55772          # Порт для UDP-обнаружения
HEARTBEAT_SEC   = 15             # Пульс каждые N секунд
NODE_TIMEOUT    = 45             # Нода считается мёртвой через N секунд
VERSION         = "1.0.0"
NETWORK_SECRET  = os.getenv("ARGOS_NETWORK_SECRET", "argos_default_secret")


def p2p_protocol_roadmap() -> str:
    """Статус протокола и дорожная карта миграции на libp2p + ZKP."""
    return (
        "🛰️ P2P ПРОТОКОЛ ARGOS\n"
        "Текущий транспорт: UDP discovery + TCP JSON (custom).\n"
        "\n"
        "🎯 Рекомендуемый target: libp2p (совместимость с dHT, pubsub, secure transports).\n"
        "Этапы миграции:\n"
        "1) Discovery: mDNS/Kademlia вместо широковещательного UDP.\n"
        "2) Transport Security: Noise/TLS + peer identity keys.\n"
        "3) Messaging: gossipsub для событий, request-response для RPC.\n"
        "4) Data exchange: protobuf-сообщения и версионирование протокола.\n"
        "\n"
        "🔐 ZKP roadmap (перспектива):\n"
        "- Phase A: selective disclosure (минимизация персональных полей).\n"
        "- Phase B: proof-of-attribute (подтверждение факта без раскрытия значения).\n"
        "- Phase C: proof-of-policy (валидность данных/правил между нодами).\n"
        "\n"
        "Примечание: в текущей версии ZKP не активирован, это roadmap для следующей итерации."
    )


# ═══════════════════════════════════════════════════════════
# ПРОФИЛЬ НОДЫ — мощность, возраст, навыки
# ═══════════════════════════════════════════════════════════
class NodeProfile:
    def __init__(self):
        self.node_id    = self._load_or_create_id()
        self.birth      = self._load_or_create_birth()
        self.version    = VERSION
        self.os_type    = platform.system()
        self.hostname   = socket.gethostname()
        self.role       = self._resolve_role()

    def _load_or_create_id(self) -> str:
        path = "config/node_id"
        if os.path.exists(path):
            return open(path).read().strip()
        nid = str(uuid.uuid4())
        os.makedirs("config", exist_ok=True)
        open(path, "w").write(nid)
        return nid

    def _load_or_create_birth(self) -> str:
        path = "config/node_birth"
        if os.path.exists(path):
            return open(path).read().strip()
        birth = datetime.datetime.now().isoformat()
        os.makedirs("config", exist_ok=True)
        open(path, "w").write(birth)
        return birth

    def get_power(self) -> dict:
        """Вычислительная мощность ноды (0–100)."""
        cpu_free  = 100 - psutil.cpu_percent(interval=0.3)
        ram       = psutil.virtual_memory()
        ram_free  = (ram.available / ram.total) * 100
        cpu_cores = psutil.cpu_count(logical=False) or 1

        # Итоговый индекс мощности
        power_index = int(
            (cpu_free * 0.5) +
            (ram_free * 0.3) +
            min(cpu_cores * 5, 20)
        )
        return {
            "index":     power_index,
            "cpu_free":  round(cpu_free, 1),
            "ram_free":  round(ram_free, 1),
            "cpu_cores": cpu_cores,
            "ram_gb":    round(ram.total / (1024**3), 1),
        }

    def get_age_days(self) -> float:
        """Возраст ноды в днях."""
        try:
            birth = datetime.datetime.fromisoformat(self.birth)
            return (datetime.datetime.now() - birth).total_seconds() / 86400
        except Exception:
            return 0.0

    def get_authority(self) -> int:
        """Авторитет ноды = мощность × log(возраст+1). Старые и мощные — главные."""
        import math
        age   = self.get_age_days()
        power = self.get_power()["index"]
        return int(power * math.log(age + 2))

    def _resolve_role(self) -> str:
        env_role = (os.getenv("ARGOS_NODE_ROLE", "") or "").strip().lower()
        if env_role in {"gateway", "worker", "server"}:
            return env_role

        power = self.get_power()
        if power.get("cpu_cores", 1) <= 2 or power.get("ram_gb", 1.0) < 2.5:
            return "gateway"
        if power.get("cpu_cores", 1) >= 8 and power.get("ram_gb", 0.0) >= 16:
            return "server"
        return "worker"

    def get_skills(self) -> list:
        try:
            return [f[:-3] for f in os.listdir("src/skills")
                    if f.endswith(".py") and not f.startswith("__")]
        except Exception:
            return []

    def to_dict(self) -> dict:
        power = self.get_power()
        return {
            "node_id":   self.node_id,
            "birth":     self.birth,
            "age_days":  round(self.get_age_days(), 2),
            "authority": self.get_authority(),
            "version":   self.version,
            "os":        self.os_type,
            "hostname":  self.hostname,
            "role":      self.role,
            "power":     power,
            "skills":    self.get_skills(),
        }


# ═══════════════════════════════════════════════════════════
# ИЗВЕСТНЫЕ НОДЫ — реестр живых участников сети
# ═══════════════════════════════════════════════════════════
class NodeRegistry:
    def __init__(self):
        self._nodes: dict[str, dict] = {}  # node_id → profile + last_seen
        self._lock = threading.Lock()

    def update(self, profile: dict, addr: str):
        nid = profile.get("node_id")
        if not nid:
            return
        with self._lock:
            self._nodes[nid] = {
                **profile,
                "addr":      addr,
                "last_seen": time.time(),
            }

    def remove_dead(self):
        now = time.time()
        with self._lock:
            dead = [nid for nid, n in self._nodes.items()
                    if now - n["last_seen"] > NODE_TIMEOUT]
            for nid in dead:
                del self._nodes[nid]

    def all(self) -> list:
        with self._lock:
            return list(self._nodes.values())

    def count(self) -> int:
        return len(self._nodes)

    def get_master(self) -> Optional[dict]:
        """Нода с наибольшим авторитетом — главная."""
        nodes = self.all()
        if not nodes:
            return None
        return max(nodes, key=lambda n: n.get("authority", 0))

    def total_power(self) -> int:
        """Суммарная мощность всей сети."""
        return sum(n.get("power", {}).get("index", 0) for n in self.all())

    def report(self, self_profile: dict) -> str:
        nodes = self.all()
        master = self.get_master()
        total  = self.total_power() + self_profile.get("power", {}).get("index", 0)

        lines = [
            f"🌐 ARGOS NETWORK — {len(nodes) + 1} нод(а) онлайн",
            f"   Суммарная мощность: {total}/100",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"👁️ ЭТА НОДА:",
            f"   ID:        {self_profile['node_id'][:8]}...",
            f"   Возраст:   {self_profile['age_days']:.1f} дней",
            f"   Мощность:  {self_profile['power']['index']}/100",
            f"   Авторитет: {self_profile['authority']}",
            f"   Навыки:    {len(self_profile['skills'])}",
        ]

        if master:
            is_master = master["node_id"] == self_profile["node_id"]
            lines.append(f"\n👑 МАСТЕР: {'ЭТА НОДА ✅' if is_master else master['hostname']}")

        if nodes:
            lines.append(f"\n📡 СОСЕДНИЕ НОДЫ:")
            for n in sorted(nodes, key=lambda x: -x.get("authority", 0)):
                age   = n.get("age_days", 0)
                pw    = n.get("power", {}).get("index", 0)
                auth  = n.get("authority", 0)
                host  = n.get("hostname", "unknown")
                addr  = n.get("addr", "?")
                sk    = len(n.get("skills", []))
                lines.append(
                    f"   🔹 {host} ({addr})\n"
                    f"      Возраст: {age:.1f}д | Мощность: {pw}/100 | Авторитет: {auth} | Навыки: {sk}"
                )

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# РАСПРЕДЕЛИТЕЛЬ ЗАДАЧ
# ═══════════════════════════════════════════════════════════
class TaskDistributor:
    """Выбирает лучшую ноду для выполнения задачи."""

    HEAVY_KEYWORDS = (
        "vision", "камер", "изображ", "скрин", "compile", "компиля",
        "build", "прошив", "firmware", "video", "render", "train"
    )

    def __init__(self, registry: NodeRegistry, self_profile: NodeProfile, bridge=None):
        self.registry = registry
        self.me = self_profile
        self.bridge = bridge
        self.weights = {
            "auth": float(os.getenv("ARGOS_P2P_WEIGHT_AUTH", "0.5") or "0.5"),
            "power": float(os.getenv("ARGOS_P2P_WEIGHT_POWER", "0.5") or "0.5"),
            "heavy_auth": float(os.getenv("ARGOS_P2P_WEIGHT_HEAVY_AUTH", "0.55") or "0.55"),
            "heavy_power": float(os.getenv("ARGOS_P2P_WEIGHT_HEAVY_POWER", "0.45") or "0.45"),
            "heavy_ram": float(os.getenv("ARGOS_P2P_WEIGHT_HEAVY_RAM", "0.4") or "0.4"),
            "queue_penalty": float(os.getenv("ARGOS_P2P_WEIGHT_QUEUE_PENALTY", "2.5") or "2.5"),
            "inflight_penalty": float(os.getenv("ARGOS_P2P_WEIGHT_INFLIGHT_PENALTY", "1.5") or "1.5"),
            "rtt_penalty": float(os.getenv("ARGOS_P2P_WEIGHT_RTT_PENALTY", "0.04") or "0.04"),
            "error_penalty": float(os.getenv("ARGOS_P2P_WEIGHT_ERROR_PENALTY", "50") or "50"),
            "stale_penalty": float(os.getenv("ARGOS_P2P_WEIGHT_STALE_PENALTY", "0.166") or "0.166"),
        }
        self.failover_limit = max(1, min(int(os.getenv("ARGOS_P2P_FAILOVER_LIMIT", "3") or "3"), 5))

    def update_weight(self, name: str, value: float) -> tuple[bool, str]:
        key = (name or "").strip().lower()
        if key not in self.weights:
            return False, f"Неизвестный вес: {key}"
        try:
            self.weights[key] = float(value)
            return True, f"✅ Вес '{key}' = {self.weights[key]:.3f}"
        except Exception:
            return False, "Некорректное значение веса"

    def set_failover_limit(self, value: int) -> str:
        self.failover_limit = max(1, min(int(value), 5))
        return f"✅ P2P failover limit = {self.failover_limit}"

    def tuning_report(self) -> str:
        lines = ["⚙️ P2P ROUTING TUNING:"]
        lines.append(f"  failover_limit: {self.failover_limit}")
        for key in sorted(self.weights.keys()):
            lines.append(f"  {key}: {self.weights[key]:.3f}")
        return "\n".join(lines)

    def _infer_task_type(self, prompt: str) -> str:
        low = (prompt or "").lower()
        if any(k in low for k in ("валид", "verify", "verification", "финал", "finalize", "проверь")):
            return "verify"
        if any(k in low for k in ("draft", "чернов", "наброс", "быстрый вариант")):
            return "draft"
        if any(k in low for k in self.HEAVY_KEYWORDS):
            return "heavy"
        return "ai"

    def _consensus_role(self, node: dict, all_nodes: list[dict]) -> str:
        """
        Ролевая маршрутизация по формуле авторитета.
        
        Правила:
          - Нода с наибольшим authority → Verifier-Node (валидация)
          - Ноды с role='gateway' или cpu_cores<=2 → Drafter-Node (черновики)
          - Остальные → Drafter-Node (по умолчанию)
          - При равном authority — Verifier тот, у кого RAM больше
        """
        if not all_nodes:
            return "drafter"

        # «Слабые» ноды всегда Drafter — шлюзы, маломощные
        node_role = str(node.get("role", "worker"))
        node_cores = int(node.get("power", {}).get("cpu_cores", 1) or 1)
        node_ram = float(node.get("power", {}).get("ram_gb", 0.0) or 0.0)
        if node_role == "gateway" or node_cores <= 2 or node_ram < 3.0:
            return "drafter"

        # Самая мощная нода — Verifier (Master)
        master = max(all_nodes, key=lambda n: (
            float(n.get("authority", 0.0) or 0.0),
            float(n.get("power", {}).get("ram_gb", 0.0) or 0.0),
        ))
        if node.get("node_id") == master.get("node_id"):
            return "verifier"

        return "drafter"

    def _score_node(self, node: dict, task_type: str, all_nodes: list[dict] | None = None) -> float:
        if all_nodes is None:
            all_nodes = [self.me.to_dict()] + self.registry.all()
        power = float(node.get("power", {}).get("index", 0.0))
        auth = float(node.get("authority", 0.0))
        ram_gb = float(node.get("power", {}).get("ram_gb", 0.0))
        role = str(node.get("role", "worker"))
        consensus_role = self._consensus_role(node, all_nodes)
        queue_depth = float(node.get("queue_depth", 0.0))
        inflight = float(node.get("inflight", 0.0))
        rtt_ms = float(node.get("rtt_ms", 80.0) or 80.0)
        error_rate = float(node.get("error_rate", 0.0) or 0.0)
        freshness_sec = max(0.0, time.time() - float(node.get("state_ts", node.get("last_seen", time.time()))))

        queue_penalty = min(queue_depth * self.weights["queue_penalty"], 35.0)
        inflight_penalty = min(inflight * self.weights["inflight_penalty"], 18.0)
        rtt_penalty = min(rtt_ms * self.weights["rtt_penalty"], 18.0)
        error_penalty = min(error_rate * self.weights["error_penalty"], 40.0)
        stale_penalty = min(freshness_sec * self.weights["stale_penalty"], 15.0)
        dynamic_penalty = queue_penalty + inflight_penalty + rtt_penalty + error_penalty + stale_penalty

        if task_type == "heavy":
            role_bonus = 22.0 if role == "server" else (8.0 if role == "worker" else -25.0)
            return (
                (auth * self.weights["heavy_auth"]) +
                (power * self.weights["heavy_power"]) +
                role_bonus +
                min(ram_gb, 64.0) * self.weights["heavy_ram"] -
                dynamic_penalty
            )

        if task_type == "verify":
            verify_bonus = 36.0 if consensus_role == "verifier" else -18.0
            verify_role_bonus = 8.0 if role == "server" else (2.0 if role == "worker" else -16.0)
            return (auth * 0.75) + (power * 0.25) + verify_bonus + verify_role_bonus - dynamic_penalty

        if task_type == "draft":
            drafter_bonus = 18.0 if consensus_role == "drafter" else -35.0
            weak_node_bias = max(0.0, 65.0 - power) * 0.22
            gateway_bias = 8.0 if role == "gateway" else 0.0
            return (auth * 0.35) + weak_node_bias + drafter_bonus + gateway_bias - (dynamic_penalty * 0.7)

        if task_type == "old":
            return float(node.get("age_days", 0.0)) * 10.0 + auth - (dynamic_penalty * 0.7)

        return (auth * self.weights["auth"]) + (power * self.weights["power"]) - dynamic_penalty

    def pick_node_for(self, task_type: str = "ai") -> dict:
        """
        task_type:
          'ai'    — нужна максимальная мощность CPU/RAM
          'store' — нужно место на диске
          'old'   — нужен авторитет (старая нода)
        """
        nodes = self.registry.all()
        me    = self.me.to_dict()
        all_  = [me] + nodes

        if task_type == "heavy":
            candidates = [
                n for n in all_
                if n.get("role", "worker") != "gateway"
                and n.get("power", {}).get("index", 0) >= 45
                and n.get("power", {}).get("ram_gb", 0) >= 4
            ]
            if not candidates:
                candidates = all_
            best = max(candidates, key=lambda n: self._score_node(n, "heavy"))
        elif task_type == "ai":
            best = max(all_, key=lambda n: self._score_node(n, "ai", all_))
        elif task_type == "verify":
            best = max(all_, key=lambda n: self._score_node(n, "verify", all_))
        elif task_type == "draft":
            drafters = [n for n in all_ if self._consensus_role(n, all_) == "drafter"]
            if not drafters:
                drafters = all_
            best = max(drafters, key=lambda n: self._score_node(n, "draft", all_))
        elif task_type == "old":
            best = max(all_, key=lambda n: n.get("age_days", 0))
        else:
            best = max(all_, key=lambda n: self._score_node(n, task_type, all_))

        is_me = best["node_id"] == me["node_id"]
        return {"node": best, "is_local": is_me, "task_type": task_type}

    def top_candidates(self, task_type: str = "ai", limit: int = 2) -> list[dict]:
        nodes = self.registry.all()
        me = self.me.to_dict()
        all_nodes = [me] + nodes
        ranked = sorted(all_nodes, key=lambda n: self._score_node(n, task_type, all_nodes), reverse=True)
        return ranked[:max(1, min(limit, 5))]

    def _exec_local(self, prompt: str, resolved_type: str, core=None) -> str:
        if not core:
            return "[LOCAL] Ядро не подключено."
        started = time.time()
        try:
            res = core._ask_gemini("Ты Аргос.", prompt) or \
                  core._ask_ollama("Ты Аргос.", prompt) or \
                  "Нет ответа от ИИ."
            if self.bridge:
                self.bridge.record_local_query((time.time() - started) * 1000.0, ok=True)
            return f"[LOCAL:{resolved_type}] {res}"
        except Exception as e:
            if self.bridge:
                self.bridge.record_local_query((time.time() - started) * 1000.0, ok=False)
            return f"[LOCAL FAIL:{resolved_type}] {e}"

    def _exec_remote(self, node: dict, prompt: str, resolved_type: str) -> tuple[bool, str]:
        addr = node.get("addr", "")
        if not addr:
            return False, "missing addr"
        req_id = str(uuid.uuid4())
        started = time.time()
        try:
            sock = socket.socket()
            sock.settimeout(8)
            sock.connect((addr, P2P_PORT))
            sock.sendall(json.dumps({
                "action": "query",
                "prompt": prompt,
                "task_type": resolved_type,
                "request_id": req_id,
                "secret": NETWORK_SECRET,
            }).encode())
            raw = sock.recv(65536)
            sock.close()
            data = json.loads(raw.decode() or "{}")
            elapsed = (time.time() - started) * 1000.0
            if self.bridge:
                self.bridge.registry.update({**node, "rtt_ms": round(elapsed, 1), "state_ts": time.time()}, addr)
            if data.get("error"):
                return False, str(data.get("error"))
            answer = data.get("answer", "Нет ответа")
            return True, f"[{node.get('hostname', 'remote')}:{resolved_type}] {answer}"
        except Exception as e:
            return False, str(e)

    def route_task(self, prompt: str, core=None, task_type: str = None) -> str:
        """Направляет AI-запрос на оптимальную ноду с failover."""
        resolved_type = task_type or self._infer_task_type(prompt)
        candidates = self.top_candidates(resolved_type, limit=self.failover_limit)
        failures = []

        for node in candidates:
            if node.get("node_id") == self.me.node_id:
                return self._exec_local(prompt, resolved_type, core=core)

            ok, response = self._exec_remote(node, prompt, resolved_type)
            if ok:
                return response
            failures.append(f"{node.get('hostname', 'remote')}: {response}")

        local_fallback = self._exec_local(prompt, resolved_type, core=core)
        if not failures:
            return local_fallback
        return f"{local_fallback}\n[ROUTE FAILOVER] " + " | ".join(failures[:3])


# ═══════════════════════════════════════════════════════════
# P2P МОСТ — сервер + клиент + пульс
# ═══════════════════════════════════════════════════════════
class ArgosBridge:
    def __init__(self, core=None):
        self.core        = core
        self.profile     = NodeProfile()
        self.registry    = NodeRegistry()
        self.distributor = TaskDistributor(self.registry, self.profile, bridge=self)
        self._running    = False
        self._local_ip   = self._get_local_ip()
        self._metrics_lock = threading.Lock()
        self._inflight = 0
        self._done = 0
        self._errors = 0
        self._latency_ms = deque(maxlen=200)
        self._request_cache: dict[str, tuple[float, str]] = {}
        self._request_cache_lock = threading.Lock()
        self._bind_task_queue_failover()

    def _bind_task_queue_failover(self):
        if not self.core or not getattr(self.core, "task_queue", None):
            return
        try:
            msg = self.core.task_queue.set_heavy_failover(
                guard=self._should_preempt_heavy,
                runner=self._offload_heavy_task,
            )
            print(f"[P2P QUEUE]: {msg}")
        except Exception as e:
            print(f"[P2P QUEUE]: bind failover error: {e}")

    def _should_preempt_heavy(self, task) -> bool:
        if not self._running:
            return False
        if not self.core:
            return False
        if not self.registry.all():
            return False
        predictive = bool(getattr(self.core, "_homeostasis_preemptive_heavy", False))
        blocked = bool(getattr(self.core, "_homeostasis_block_heavy", False))
        return predictive or blocked

    def _offload_heavy_task(self, task) -> tuple[bool, str]:
        if not self._running:
            return False, "P2P bridge is not running"

        candidates = self.distributor.top_candidates("heavy", limit=self.distributor.failover_limit)
        failures = []
        task_data = {
            "kind": str(getattr(task, "kind", "") or ""),
            "payload": dict(getattr(task, "payload", {}) or {}),
            "task_class": str(getattr(task, "task_class", "heavy") or "heavy"),
            "task_id": int(getattr(task, "task_id", 0) or 0),
        }

        for node in candidates:
            if node.get("node_id") == self.profile.node_id:
                continue
            ok, response = self._exec_remote_task(node, task_data)
            if ok:
                return True, response
            failures.append(f"{node.get('hostname', 'remote')}: {response}")

        return False, " | ".join(failures[:3]) if failures else "no remote candidates"

    def _exec_remote_task(self, node: dict, task_data: dict) -> tuple[bool, str]:
        addr = node.get("addr", "")
        if not addr:
            return False, "missing addr"
        req_id = str(uuid.uuid4())
        started = time.time()
        try:
            sock = socket.socket()
            sock.settimeout(10)
            sock.connect((addr, P2P_PORT))
            sock.sendall(json.dumps({
                "action": "run_task",
                "task": task_data,
                "request_id": req_id,
                "secret": NETWORK_SECRET,
            }).encode())
            raw = sock.recv(65536)
            sock.close()
            data = json.loads(raw.decode() or "{}")
            elapsed = (time.time() - started) * 1000.0
            self.registry.update({**node, "rtt_ms": round(elapsed, 1), "state_ts": time.time()}, addr)

            if data.get("ok"):
                return True, str(data.get("output", "remote task done"))
            return False, str(data.get("error") or "remote task failed")
        except Exception as e:
            return False, str(e)

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _sign(self, data: dict) -> str:
        raw = json.dumps(data, sort_keys=True) + NETWORK_SECRET
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def start(self) -> str:
        self._running = True
        threading.Thread(target=self._udp_broadcaster, daemon=True).start()
        threading.Thread(target=self._udp_listener,    daemon=True).start()
        threading.Thread(target=self._tcp_server,      daemon=True).start()
        threading.Thread(target=self._heartbeat_loop,  daemon=True).start()
        return (
            f"🌐 P2P-мост запущен\n"
            f"   IP:       {self._local_ip}:{P2P_PORT}\n"
            f"   Нода ID:  {self.profile.node_id[:8]}...\n"
            f"   Возраст:  {self.profile.get_age_days():.2f} дней\n"
            f"   Мощность: {self.profile.get_power()['index']}/100\n"
            f"   Авторитет:{self.profile.get_authority()}"
        )

    def _cache_get(self, req_id: str) -> Optional[str]:
        if not req_id:
            return None
        now = time.time()
        with self._request_cache_lock:
            hit = self._request_cache.get(req_id)
            if not hit:
                return None
            ts, answer = hit
            if now - ts > 120:
                self._request_cache.pop(req_id, None)
                return None
            return answer

    def _cache_put(self, req_id: str, answer: str):
        if not req_id:
            return
        now = time.time()
        with self._request_cache_lock:
            self._request_cache[req_id] = (now, answer)
            stale = [k for k, (ts, _) in self._request_cache.items() if now - ts > 120]
            for key in stale:
                self._request_cache.pop(key, None)

    def _runtime_status(self) -> dict:
        with self._metrics_lock:
            p95 = 0.0
            if self._latency_ms:
                sorted_lat = sorted(self._latency_ms)
                idx = int(0.95 * (len(sorted_lat) - 1))
                p95 = float(sorted_lat[idx])
            total = self._done + self._errors
            err_rate = (self._errors / total) if total > 0 else 0.0
            consensus_role = self.distributor._consensus_role(
                self.profile.to_dict(),
                [self.profile.to_dict()] + self.registry.all(),
            )
            return {
                "queue_depth": 0,
                "inflight": self._inflight,
                "p95_ms": round(p95, 1),
                "error_rate": round(err_rate, 3),
                "consensus_role": consensus_role,
                "state_ts": time.time(),
            }

    def record_local_query(self, duration_ms: float, ok: bool = True):
        with self._metrics_lock:
            self._latency_ms.append(max(0.0, float(duration_ms)))
            if ok:
                self._done += 1
            else:
                self._errors += 1

    def _remote_status(self, addr: str) -> Optional[dict]:
        try:
            started = time.time()
            sock = socket.socket()
            sock.settimeout(4)
            sock.connect((addr, P2P_PORT))
            sock.sendall(json.dumps({"action": "status", "secret": NETWORK_SECRET}).encode())
            data = json.loads(sock.recv(65536).decode() or "{}")
            sock.close()
            data["rtt_ms"] = round((time.time() - started) * 1000.0, 1)
            data["state_ts"] = time.time()
            return data
        except Exception:
            return None

    def stop(self):
        self._running = False

    # ── UDP ОБНАРУЖЕНИЕ (broadcast) ───────────────────────
    def _udp_broadcaster(self):
        """Рассылает 'Я здесь!' по локальной сети каждые N сек."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self._running:
            try:
                payload = json.dumps({
                    "type":    "ARGOS_HELLO",
                    "profile": self.profile.to_dict(),
                    "sign":    self._sign(self.profile.to_dict()),
                }).encode()
                sock.sendto(payload, ("<broadcast>", BROADCAST_PORT))
            except Exception:
                pass
            time.sleep(HEARTBEAT_SEC)
        sock.close()

    def _udp_listener(self):
        """Слушает broadcast-сообщения от других нод."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", BROADCAST_PORT))
        except Exception as e:
            print(f"[P2P UDP]: Не удалось открыть порт {BROADCAST_PORT}: {e}")
            return
        sock.settimeout(2)
        while self._running:
            try:
                data, addr = sock.recvfrom(4096)
                msg = json.loads(data.decode())
                if msg.get("type") != "ARGOS_HELLO":
                    continue
                profile = msg.get("profile", {})
                if profile.get("node_id") == self.profile.node_id:
                    continue  # Игнорируем себя
                self.registry.update(profile, addr[0])
            except socket.timeout:
                self.registry.remove_dead()
            except Exception:
                pass
        sock.close()

    # ── TCP СЕРВЕР — принимает запросы от других нод ──────
    def _tcp_server(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("", P2P_PORT))
            srv.listen(10)
        except Exception as e:
            print(f"[P2P TCP]: Не удалось открыть порт {P2P_PORT}: {e}")
            return
        srv.settimeout(2)
        while self._running:
            try:
                conn, addr = srv.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(conn, addr[0]),
                    daemon=True,
                ).start()
            except socket.timeout:
                pass
            except Exception:
                pass
        srv.close()

    def _handle_client(self, conn: socket.socket, addr: str):
        try:
            raw  = conn.recv(65536)
            msg  = json.loads(raw.decode())

            # Проверка секрета
            if msg.get("secret") != NETWORK_SECRET:
                conn.sendall(json.dumps({"error": "Unauthorized"}).encode())
                return

            action = msg.get("action", "query")

            if action == "query":
                prompt = msg.get("prompt", "")
                req_id = str(msg.get("request_id", "") or "").strip()
                cached = self._cache_get(req_id)
                if cached is not None:
                    conn.sendall(json.dumps({
                        "answer": cached,
                        "cached": True,
                        "node_id": self.profile.node_id,
                        "host": self.profile.hostname,
                    }).encode())
                    return

                with self._metrics_lock:
                    self._inflight += 1
                started = time.time()
                if self.core:
                    answer = (self.core._ask_gemini("Ты Аргос.", prompt) or
                              self.core._ask_ollama("Ты Аргос.", prompt) or
                              "Нет ответа от ИИ.")
                else:
                    answer = "Ядро не подключено на этой ноде."

                elapsed = (time.time() - started) * 1000.0
                self.record_local_query(elapsed, ok=True)
                with self._metrics_lock:
                    self._inflight = max(0, self._inflight - 1)
                self._cache_put(req_id, answer)
                conn.sendall(json.dumps({
                    "answer":  answer,
                    "node_id": self.profile.node_id,
                    "host":    self.profile.hostname,
                    "runtime": self._runtime_status(),
                }).encode())

            elif action == "sync_skills":
                # Запрашивающая нода хочет получить список наших навыков
                skills = self.profile.get_skills()
                conn.sendall(json.dumps({"skills": skills}).encode())

            elif action == "get_skill":
                # Передаём файл навыка
                skill_name = msg.get("skill", "")
                path = f"src/skills/{skill_name}.py"
                if os.path.exists(path) and not skill_name.startswith(".."):
                    code = open(path, encoding="utf-8").read()
                    conn.sendall(json.dumps({"code": code, "name": skill_name}).encode())
                else:
                    conn.sendall(json.dumps({"error": "Skill not found"}).encode())

            elif action == "status":
                profile = self.profile.to_dict()
                profile.update(self._runtime_status())
                conn.sendall(json.dumps(profile).encode())

            elif action == "run_task":
                task_data = msg.get("task", {}) if isinstance(msg.get("task", {}), dict) else {}
                kind = str(task_data.get("kind", "logic.command") or "logic.command")
                payload = task_data.get("payload", {}) if isinstance(task_data.get("payload", {}), dict) else {}
                task_class = str(task_data.get("task_class", "heavy") or "heavy")

                if not self.core or not getattr(self.core, "task_queue", None):
                    conn.sendall(json.dumps({"ok": False, "error": "task queue unavailable"}).encode())
                    return

                runner = self.core.task_queue._runners.get(kind)
                if not runner:
                    conn.sendall(json.dumps({"ok": False, "error": f"runner not found for kind={kind}"}).encode())
                    return

                with self._metrics_lock:
                    self._inflight += 1
                started = time.time()
                try:
                    task_stub = SimpleNamespace(
                        task_id=int(task_data.get("task_id", 0) or 0),
                        kind=kind,
                        payload=payload,
                        task_class=task_class,
                        attempt=0,
                        max_retries=0,
                    )
                    result = runner(task_stub)
                    output = str(result) if result is not None else ""
                    elapsed = (time.time() - started) * 1000.0
                    self.record_local_query(elapsed, ok=True)
                    with self._metrics_lock:
                        self._inflight = max(0, self._inflight - 1)
                    conn.sendall(json.dumps({
                        "ok": True,
                        "output": output,
                        "runtime": self._runtime_status(),
                    }).encode())
                except Exception as e:
                    with self._metrics_lock:
                        self._errors += 1
                        self._inflight = max(0, self._inflight - 1)
                    conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode())

        except Exception as e:
            with self._metrics_lock:
                self._errors += 1
                self._inflight = max(0, self._inflight - 1)
            try:
                conn.sendall(json.dumps({"error": str(e)}).encode())
            except Exception:
                pass
        finally:
            conn.close()

    # ── ПУЛЬС — периодические задачи ─────────────────────
    def _heartbeat_loop(self):
        while self._running:
            time.sleep(HEARTBEAT_SEC)
            self.registry.remove_dead()
            for node in self.registry.all():
                addr = node.get("addr")
                if not addr:
                    continue
                snap = self._remote_status(addr)
                if snap and snap.get("node_id"):
                    self.registry.update(snap, addr)

    # ── ПУБЛИЧНЫЙ API ─────────────────────────────────────
    def network_status(self) -> str:
        return self.registry.report(self.profile.to_dict())

    def routing_tuning_report(self) -> str:
        return self.distributor.tuning_report()

    def set_routing_weight(self, name: str, value: float) -> str:
        ok, message = self.distributor.update_weight(name, value)
        return message if ok else f"❌ {message}"

    def set_failover_limit(self, value: int) -> str:
        try:
            return self.distributor.set_failover_limit(int(value))
        except Exception:
            return "❌ Формат: p2p failover [1..5]"

    def network_telemetry(self) -> str:
        me = self.profile.to_dict()
        me.update(self._runtime_status())
        nodes = self.registry.all()
        acceptance = get_acceptance_snapshot(window=120)
        all_nodes = [me] + nodes

        # Acceptance Rate breakdown
        acc_rate = float(acceptance.get('rate', 1.0))
        acc_samples = int(acceptance.get('samples', 0) or 0)
        acc_avg_sim = float(acceptance.get('avg_similarity', 1.0))

        lines = [
            "📊 P2P TELEMETRY",
            f"  Local: {me.get('hostname')} role={me.get('role')} power={me.get('power',{}).get('index',0)}",
            f"  Local consensus role: {me.get('consensus_role','drafter')}",
            f"  Local runtime: inflight={me.get('inflight',0)} p95={me.get('p95_ms',0)}ms error_rate={me.get('error_rate',0)}",
            "",
            "  📈 ACCEPTANCE RATE:",
            f"    Rate(120s): {acc_rate*100:.1f}% ({acceptance.get('accepted',0)}/{acc_samples})",
            f"    Avg similarity: {acc_avg_sim:.3f}",
            f"    Window: {acceptance.get('window_sec',120)}s",
        ]

        # Per-drafter quality из metrik
        try:
            from src.observability import Metrics as ObsMetrics
            snap = ObsMetrics.snapshot()
            drafter_gauges = {k: v for k, v in snap.get("gauges", {}).items()
                             if k.startswith("drafter.last_similarity.")}
            if drafter_gauges:
                lines.append("")
                lines.append("  🎯 PER-DRAFTER QUALITY:")
                for key, sim in sorted(drafter_gauges.items()):
                    drafter_name = key.replace("drafter.last_similarity.", "")
                    lines.append(f"    {drafter_name}: similarity={sim:.3f}")
        except Exception:
            pass

        lines.append("")
        lines.append(f"  Known remote nodes: {len(nodes)}")
        lines.append("")
        lines.append("  Scores (ai/heavy/draft/verify):")

        ranked = sorted(
            all_nodes,
            key=lambda n: self.distributor._score_node(n, "ai", all_nodes),
            reverse=True
        )
        for node in ranked[:8]:
            ai_score = self.distributor._score_node(node, "ai", all_nodes)
            heavy_score = self.distributor._score_node(node, "heavy", all_nodes)
            draft_score = self.distributor._score_node(node, "draft", all_nodes)
            verify_score = self.distributor._score_node(node, "verify", all_nodes)
            consensus_role = self.distributor._consensus_role(node, all_nodes)
            lines.append(
                f"  - {node.get('hostname','?')}[{node.get('role','worker')}] "
                f"consensus={consensus_role} "
                f"ai={ai_score:.1f} heavy={heavy_score:.1f} "
                f"draft={draft_score:.1f} verify={verify_score:.1f} "
                f"rtt={float(node.get('rtt_ms',0.0) or 0.0):.1f}ms "
                f"inflight={int(node.get('inflight',0) or 0)} "
                f"err={float(node.get('error_rate',0.0) or 0.0):.3f}"
            )
        lines.append("")
        lines.append(self.distributor.tuning_report())
        return "\n".join(lines)

    def route_query(self, prompt: str, task_type: str = None) -> str:
        """Отправляет AI-запрос на наиболее мощную ноду в сети."""
        return self.distributor.route_task(prompt, self.core, task_type=task_type)

    def sync_skills_from_network(self) -> str:
        """Загружает навыки от всех нод в сети."""
        nodes   = self.registry.all()
        synced  = []
        errors  = []

        for node in nodes:
            addr = node.get("addr")
            if not addr:
                continue
            try:
                # 1. Получаем список навыков удалённой ноды
                sock = socket.socket()
                sock.settimeout(5)
                sock.connect((addr, P2P_PORT))
                sock.sendall(json.dumps({
                    "action": "sync_skills",
                    "secret": NETWORK_SECRET
                }).encode())
                raw    = sock.recv(65536)
                sock.close()
                remote = json.loads(raw).get("skills", [])

                my_skills = set(self.profile.get_skills())

                # 2. Загружаем отсутствующие навыки
                for skill in remote:
                    if skill in my_skills or skill == "evolution":
                        continue
                    try:
                        s2 = socket.socket()
                        s2.settimeout(8)
                        s2.connect((addr, P2P_PORT))
                        s2.sendall(json.dumps({
                            "action": "get_skill",
                            "skill":  skill,
                            "secret": NETWORK_SECRET,
                        }).encode())
                        data = json.loads(s2.recv(65536))
                        s2.close()

                        if "code" in data:
                            path = f"src/skills/{skill}.py"
                            with open(path, "w", encoding="utf-8") as f:
                                f.write(data["code"])
                            synced.append(f"{skill} ← {node['hostname']}")
                    except Exception as e:
                        errors.append(f"{skill}: {e}")

            except Exception as e:
                errors.append(f"{node.get('hostname', addr)}: {e}")

        result = [f"🔄 СИНХРОНИЗАЦИЯ НАВЫКОВ:"]
        if synced:
            result.append(f"  Загружено: {len(synced)}")
            for s in synced:
                result.append(f"    ✅ {s}")
        else:
            result.append("  Нет новых навыков для загрузки.")
        if errors:
            result.append(f"  Ошибки: {len(errors)}")
        return "\n".join(result)

    def connect_to(self, ip: str) -> str:
        """Вручную подключиться к известной ноде по IP."""
        try:
            sock = socket.socket()
            sock.settimeout(5)
            sock.connect((ip, P2P_PORT))
            sock.sendall(json.dumps({
                "action": "status",
                "secret": NETWORK_SECRET,
            }).encode())
            data = json.loads(sock.recv(65536))
            sock.close()
            self.registry.update(data, ip)
            return (
                f"✅ Подключён к ноде:\n"
                f"   Хост:     {data.get('hostname')}\n"
                f"   ID:       {data.get('node_id','?')[:8]}...\n"
                f"   Возраст:  {data.get('age_days', 0):.1f} дней\n"
                f"   Мощность: {data.get('power',{}).get('index',0)}/100\n"
                f"   Навыки:   {len(data.get('skills',[]))}"
            )
        except Exception as e:
            return f"❌ Не удалось подключиться к {ip}: {e}"
