"""
awa_core.py — AWA-Core (Absolute Workflow Agent)
    Центральный координатор Аргоса: маршрутизация между модулями,
    каскадирование задач, принятие решений без внешних фильтров.
"""

import json
import os
import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from src.argos_logger import get_logger

log = get_logger("argos.awa")


class ModuleDescriptor:
    """Описание зарегистрированного модуля."""

    __slots__ = ("name", "ref", "priority", "category", "capabilities", "health", "last_heartbeat")

    def __init__(
        self,
        name: str,
        ref: Any,
        priority: int = 50,
        category: str = "general",
        capabilities: Optional[List[str]] = None,
    ):
        self.name = name
        self.ref = ref
        self.priority = priority
        self.category = category
        self.capabilities = capabilities or []
        self.health = "ok"
        self.last_heartbeat = time.time()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "priority": self.priority,
            "category": self.category,
            "capabilities": self.capabilities,
            "health": self.health,
            "last_heartbeat": round(self.last_heartbeat, 1),
        }


class DecisionRecord:
    """Запись решения AWA-Core."""

    __slots__ = ("ts", "intent", "routed_to", "result", "latency_ms")

    def __init__(self, intent: str, routed_to: str, result: str, latency_ms: float):
        self.ts = time.time()
        self.intent = intent
        self.routed_to = routed_to
        self.result = result
        self.latency_ms = latency_ms


class AWACore:
    """
    Absolute Workflow Agent — координирует все модули Аргоса.

    Функции:
    - Реестр модулей с приоритетами и категориями
    - Маршрутизация запросов к нужному модулю по capability
    - Каскадирование задач (цепочки action → action)
    - Статистика решений и health-мониторинг модулей
    - Автономное принятие решений без внешних фильтров
    """

    VERSION = "1.0.0"

    def __init__(self, core=None):
        self.core = core
        self._modules: Dict[str, ModuleDescriptor] = {}
        self._capability_index: Dict[str, List[str]] = defaultdict(list)
        self._pipelines: Dict[str, List[Dict[str, Any]]] = {}
        self._decision_log: deque[DecisionRecord] = deque(maxlen=500)
        self._cascade_depth_limit = int(os.getenv("AWA_CASCADE_DEPTH", "8") or "8")
        self._heartbeat_max_age_sec = float(os.getenv("AWA_HEARTBEAT_MAX_AGE", "120") or "120")
        self._heartbeat_check_interval_sec = float(os.getenv("AWA_HEARTBEAT_CHECK_INTERVAL", "15") or "15")
        self._lock = threading.Lock()
        self._running = True

        # policy: bypass, confirm, restrict
        self._policy = os.getenv("AWA_POLICY", "bypass").strip().lower()

        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        log.info(
            "AWA-Core v%s init | policy=%s | cascade_depth=%d", self.VERSION, self._policy, self._cascade_depth_limit
        )

    # ── Регистрация модулей ──────────────────────────────
    def register(
        self,
        name: str,
        ref: Any,
        *,
        priority: int = 50,
        category: str = "general",
        capabilities: Optional[List[str]] = None,
    ) -> None:
        """Регистрирует модуль в реестре AWA-Core."""
        desc = ModuleDescriptor(name, ref, priority, category, capabilities)
        with self._lock:
            self._modules[name] = desc
            for cap in desc.capabilities:
                if name not in self._capability_index[cap]:
                    self._capability_index[cap].append(name)
        log.info("AWA: зарегистрирован [%s] cat=%s caps=%s", name, category, capabilities)

    def unregister(self, name: str) -> None:
        with self._lock:
            desc = self._modules.pop(name, None)
            if desc:
                for cap in desc.capabilities:
                    lst = self._capability_index.get(cap, [])
                    if name in lst:
                        lst.remove(name)
        log.info("AWA: удалён [%s]", name)

    # ── Маршрутизация ────────────────────────────────────
    def resolve(self, capability: str) -> Optional[Any]:
        """Возвращает ссылку на лучший модуль по capability (по приоритету)."""
        with self._lock:
            names = self._capability_index.get(capability, [])
            if not names:
                return None
            candidates = [
                (self._modules[n].priority, n) for n in names if n in self._modules and self._modules[n].health == "ok"
            ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_name = candidates[0][1]
        return self._modules[best_name].ref

    def route(self, intent: str, payload: Any = None) -> str:
        """
        Маршрутизирует запрос к подходящему модулю.
        intent = capability tag (e.g. "radio_scan", "nfc_read", "purge").
        """
        t0 = time.time()
        module_ref = self.resolve(intent)
        if module_ref is None:
            rec = DecisionRecord(intent, "none", "no_module", 0)
            self._decision_log.append(rec)
            return f"⚠️ AWA: нет модуля для '{intent}'"

        # вызов handle(payload)
        result = "ok"
        try:
            if hasattr(module_ref, "handle"):
                result = module_ref.handle(intent, payload)
            elif callable(module_ref):
                result = module_ref(intent, payload)
            else:
                result = f"module {intent} not callable"
        except Exception as e:
            result = f"error: {e}"
            log.error("AWA route error [%s]: %s", intent, e)

        latency = (time.time() - t0) * 1000
        name = getattr(module_ref, "__class__", type(module_ref)).__name__
        rec = DecisionRecord(intent, name, str(result)[:120], latency)
        self._decision_log.append(rec)
        return str(result)

    # ── Каскады ──────────────────────────────────────────
    def register_pipeline(self, name: str, steps: List[Dict[str, Any]]) -> str:
        """Регистрирует каскадный pipeline по имени."""
        if not name.strip():
            return "⚠️ AWA: имя pipeline пустое"
        if not isinstance(steps, list) or not steps:
            return "⚠️ AWA: pipeline должен содержать хотя бы один шаг"
        with self._lock:
            self._pipelines[name.strip()] = steps
        return f"✅ AWA pipeline '{name.strip()}' зарегистрирован ({len(steps)} шагов)"

    def run_pipeline(self, name: str, payload: Any = None) -> List[str]:
        """Запускает зарегистрированный каскадный pipeline."""
        with self._lock:
            steps = list(self._pipelines.get(name, []))
        if not steps:
            return [f"⚠️ AWA: pipeline '{name}' не найден"]

        prepared: List[Dict[str, Any]] = []
        for step in steps:
            step_intent = str(step.get("intent", "")).strip()
            if not step_intent:
                continue
            step_payload = step.get("payload")
            if step_payload is None:
                step_payload = payload
            prepared.append({"intent": step_intent, "payload": step_payload})
        if not prepared:
            return [f"⚠️ AWA: pipeline '{name}' не содержит валидных шагов"]
        return self.cascade(prepared)

    def cascade(self, steps: List[Dict[str, Any]]) -> List[str]:
        """
        Выполняет каскад действий последовательно.
        steps = [{"intent": "radio_scan", "payload": {...}}, ...]
        Если шаг вернул ошибку, каскад останавливается.
        """
        results = []
        for i, step in enumerate(steps):
            if i >= self._cascade_depth_limit:
                results.append(f"⚠️ AWA: лимит каскада ({self._cascade_depth_limit})")
                break
            intent = step.get("intent", "")
            payload = step.get("payload")
            res = self.route(intent, payload)
            results.append(res)
            if "error" in res.lower():
                log.warning("AWA cascade stopped at step %d: %s", i, res)
                break
        return results

    # ── Heartbeat ────────────────────────────────────────
    def heartbeat(self, name: str) -> None:
        """Модуль сообщает о жизни."""
        with self._lock:
            desc = self._modules.get(name)
            if desc:
                desc.last_heartbeat = time.time()
                desc.health = "ok"

    def mark_unhealthy(self, name: str, reason: str = "") -> None:
        with self._lock:
            desc = self._modules.get(name)
            if desc:
                desc.health = f"unhealthy: {reason}" if reason else "unhealthy"
                log.warning("AWA: [%s] помечен unhealthy: %s", name, reason)

    def check_stale(self, max_age_sec: float = 120) -> List[str]:
        """Возвращает модули без heartbeat дольше max_age_sec."""
        now = time.time()
        stale = []
        with self._lock:
            for name, desc in self._modules.items():
                if (now - desc.last_heartbeat) > max_age_sec:
                    stale.append(name)
                    desc.health = "stale"
        return stale

    def _heartbeat_loop(self) -> None:
        """Фоновая проверка heartbeat модулей."""
        while self._running:
            try:
                stale = self.check_stale(self._heartbeat_max_age_sec)
                if stale:
                    log.warning("AWA heartbeat stale: %s", ", ".join(stale))
            except Exception as e:
                log.warning("AWA heartbeat loop error: %s", e)
            time.sleep(max(1.0, self._heartbeat_check_interval_sec))

    # ── Статус ───────────────────────────────────────────
    def status(self) -> str:
        with self._lock:
            total = len(self._modules)
            healthy = sum(1 for d in self._modules.values() if d.health == "ok")
            stale = sum(1 for d in self._modules.values() if d.health == "stale")
            caps = len(self._capability_index)
            pipelines = len(self._pipelines)
            decisions = len(self._decision_log)
        lines = [
            "🧠 AWA-CORE (Absolute Workflow Agent)",
            f"  Версия: {self.VERSION} | Policy: {self._policy}",
            f"  Модулей: {total} (healthy: {healthy}, stale: {stale})",
            f"  Capabilities: {caps}",
            f"  Pipelines: {pipelines}",
            f"  Решений: {decisions}",
        ]
        return "\n".join(lines)

    def pipeline_list(self) -> str:
        with self._lock:
            if not self._pipelines:
                return "🧠 AWA — PIPELINES: (нет зарегистрированных)"
            lines = ["🧠 AWA — CASCADE PIPELINES"]
            for name, steps in sorted(self._pipelines.items()):
                intents = [str(step.get("intent", "")) for step in steps if step.get("intent")]
                lines.append(f"  • {name}: {len(steps)} шагов → {', '.join(intents[:6])}")
            return "\n".join(lines)

    def module_list(self) -> str:
        with self._lock:
            if not self._modules:
                return "  (нет зарегистрированных модулей)"
            lines = ["🧠 AWA — РЕЕСТР МОДУЛЕЙ"]
            for name, desc in sorted(self._modules.items()):
                h = "🟢" if desc.health == "ok" else "🔴"
                lines.append(f"  {h} {name} [p={desc.priority}] cat={desc.category} caps={desc.capabilities}")
            return "\n".join(lines)

    def decision_history(self, last_n: int = 20) -> str:
        with self._lock:
            recent = list(self._decision_log)[-last_n:]
        if not recent:
            return "  (нет решений)"
        lines = ["🧠 AWA — ИСТОРИЯ РЕШЕНИЙ"]
        for r in recent:
            ts = time.strftime("%H:%M:%S", time.localtime(r.ts))
            lines.append(f"  [{ts}] {r.intent} → {r.routed_to} ({r.latency_ms:.0f}ms) {r.result[:60]}")
        return "\n".join(lines)

    def shutdown(self) -> None:
        self._running = False
        log.info("AWA-Core shutdown")
