"""
task_queue.py — Базовая очередь задач Аргоса
  PriorityQueue + worker pool для фонового выполнения команд.
"""
import os
import time
import queue
import threading
from dataclasses import dataclass, field
from collections import deque
from typing import Callable, Any

from src.argos_logger import get_logger

log = get_logger("argos.taskqueue")

try:
    from src.observability import Metrics, log_event, get_acceptance_snapshot
except Exception:  # pragma: no cover
    class Metrics:  # type: ignore
        @classmethod
        def inc(cls, name: str, value: int = 1, tags: dict = None):
            return None

        @classmethod
        def gauge(cls, name: str, value: float, tags: dict = None):
            return None

        @classmethod
        def observe(cls, name: str, value: float, tags: dict = None):
            return None

    def log_event(event_type: str, data: dict, source: str = "argos"):
        return None

    def get_acceptance_snapshot(window: int = 120) -> dict:  # type: ignore
        return {"rate": 1.0, "samples": 0, "accepted": 0, "rejected": 0}


@dataclass(order=True)
class TaskEnvelope:
    priority: int
    next_run_at: float
    created_at: float
    task_id: int = field(compare=False)
    kind: str = field(compare=False)
    payload: dict = field(compare=False)
    task_class: str = field(compare=False, default="ai")
    attempt: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=0)
    deadline_ts: float = field(compare=False, default=0.0)
    backoff_ms: int = field(compare=False, default=500)


class TaskQueueManager:
    TASK_CLASSES = ("system", "iot", "ai", "heavy")

    def __init__(self, worker_count: int = 2):
        self._queue: queue.PriorityQueue[TaskEnvelope] = queue.PriorityQueue()
        self._lock = threading.Lock()
        self._running = False
        self._workers: list[threading.Thread] = []
        self._next_id = 1
        self._runners: dict[str, Callable[[TaskEnvelope], Any]] = {}

        self._processed = 0
        self._failed = 0
        self._retried = 0
        self._expired = 0
        self._offloaded = 0
        self._durations_ms: deque[float] = deque(maxlen=300)
        self._results: deque[dict] = deque(maxlen=100)
        self._class_dispatch_ts: dict[str, deque[float]] = {
            name: deque(maxlen=512) for name in self.TASK_CLASSES
        }

        self._class_rps: dict[str, int] = {
            "system": max(1, min(int(os.getenv("ARGOS_TASK_RPS_SYSTEM", "8") or "8"), 100)),
            "iot": max(1, min(int(os.getenv("ARGOS_TASK_RPS_IOT", "6") or "6"), 100)),
            "ai": max(1, min(int(os.getenv("ARGOS_TASK_RPS_AI", "3") or "3"), 100)),
            "heavy": max(1, min(int(os.getenv("ARGOS_TASK_RPS_HEAVY", "1") or "1"), 100)),
        }
        self._baseline_ai_rps = self._class_rps["ai"]
        self._acceptance_floor = max(0.1, min(float(os.getenv("ARGOS_ACCEPTANCE_FLOOR", "0.50") or "0.50"), 0.95))
        self._acceptance_samples_min = max(3, min(int(os.getenv("ARGOS_ACCEPTANCE_MIN_SAMPLES", "8") or "8"), 120))
        self._backpressure_check_sec = max(5, int(os.getenv("ARGOS_BACKPRESSURE_CHECK_SEC", "20") or "20"))
        self._last_backpressure_check_ts = 0.0
        self._last_backpressure_action_ts = 0.0

        self.default_retries = max(0, min(int(os.getenv("ARGOS_TASK_RETRIES", "1") or "1"), 10))
        self.default_deadline_sec = max(0, min(int(os.getenv("ARGOS_TASK_DEADLINE_SEC", "120") or "120"), 3600))
        self.default_backoff_ms = max(50, min(int(os.getenv("ARGOS_TASK_BACKOFF_MS", "500") or "500"), 15000))

        env_workers = int(os.getenv("ARGOS_TASK_WORKERS", str(worker_count)) or str(worker_count))
        self.worker_count = max(1, min(env_workers, 16))

        self._heavy_preemptive_guard: Callable[[TaskEnvelope], bool] | None = None
        self._heavy_failover_runner: Callable[[TaskEnvelope], tuple[bool, str]] | None = None
        self._idle_learning_handler: Callable[[bool], tuple[bool, str] | None] | None = None
        self._idle_learning_min_sec = max(15, int(os.getenv("ARGOS_IDLE_LEARNING_MIN_SEC", "60") or "60"))
        self._last_idle_learning_ts = 0.0

    def register_runner(self, kind: str, runner: Callable[[TaskEnvelope], Any]):
        if not kind or not callable(runner):
            return
        self._runners[kind] = runner

    def set_heavy_failover(self,
                           guard: Callable[[TaskEnvelope], bool] | None,
                           runner: Callable[[TaskEnvelope], tuple[bool, str]] | None) -> str:
        self._heavy_preemptive_guard = guard if callable(guard) else None
        self._heavy_failover_runner = runner if callable(runner) else None
        if self._heavy_preemptive_guard and self._heavy_failover_runner:
            return "✅ TaskQueue heavy failover подключён."
        return "ℹ️ TaskQueue heavy failover отключён."

    def register_idle_learning_handler(self, handler: Callable[[bool], tuple[bool, str] | None] | None) -> str:
        self._idle_learning_handler = handler if callable(handler) else None
        if self._idle_learning_handler:
            return "✅ TaskQueue idle-learning handler подключён."
        return "ℹ️ TaskQueue idle-learning handler отключён."

    def start(self) -> str:
        if self._running:
            return "🧵 TaskQueue уже активна."
        self._running = True
        for idx in range(self.worker_count):
            thread = threading.Thread(target=self._worker_loop, args=(idx + 1,), daemon=True)
            self._workers.append(thread)
            thread.start()
        log.info("TaskQueue: ON (%d workers)", self.worker_count)
        return f"🧵 TaskQueue запущена ({self.worker_count} workers)."

    def stop(self) -> str:
        self._running = False
        return "🧵 TaskQueue остановлена."

    def submit(self, kind: str, payload: dict, priority: int = 5) -> int:
        return self.submit_ex(
            kind=kind,
            payload=payload,
            priority=priority,
            task_class="ai",
            max_retries=self.default_retries,
            deadline_sec=self.default_deadline_sec,
            backoff_ms=self.default_backoff_ms,
        )

    def submit_ex(self, kind: str, payload: dict, priority: int = 5, task_class: str = "ai",
                  max_retries: int = 1, deadline_sec: int = 120, backoff_ms: int = 500) -> int:
        with self._lock:
            task_id = self._next_id
            self._next_id += 1
        now = time.time()
        retries = max(0, min(int(max_retries), 10))
        ttl = max(0, min(int(deadline_sec), 3600))
        backoff = max(50, min(int(backoff_ms), 15000))
        normalized_class = self._normalize_class(task_class)
        env = TaskEnvelope(
            priority=self._priority_with_class_bias(int(priority), normalized_class),
            next_run_at=now,
            created_at=now,
            task_id=task_id,
            kind=kind,
            task_class=normalized_class,
            payload=payload or {},
            attempt=0,
            max_retries=retries,
            deadline_ts=(now + ttl) if ttl > 0 else 0.0,
            backoff_ms=backoff,
        )
        self._queue.put(env)
        Metrics.inc("taskqueue.submitted", tags={"kind": kind, "class": normalized_class})
        Metrics.gauge("taskqueue.size", float(self._queue.qsize()))
        log_event("taskqueue_submitted", {
            "task_id": task_id,
            "kind": kind,
            "class": normalized_class,
            "priority": env.priority,
            "max_retries": retries,
            "deadline_sec": ttl,
        }, source="task_queue")
        return task_id

    def _worker_loop(self, worker_id: int):
        while self._running:
            try:
                task = self._queue.get(timeout=1)
            except queue.Empty:
                now = time.time()
                self._run_idle_learning_cycle(now, force=False)
                self._check_acceptance_backpressure(now)
                continue

            now = time.time()
            if task.next_run_at > now:
                self._queue.put(task)
                self._queue.task_done()
                time.sleep(min(task.next_run_at - now, 0.2))
                continue

            wait_sec = self._rate_wait_seconds(task.task_class, now)
            if wait_sec > 0:
                task.next_run_at = now + wait_sec
                self._queue.put(task)
                self._queue.task_done()
                time.sleep(min(wait_sec, 0.2))
                continue
            self._mark_dispatched(task.task_class, now)

            if task.deadline_ts > 0 and now > task.deadline_ts:
                self._expired += 1
                self._results.appendleft({
                    "id": task.task_id,
                    "kind": task.kind,
                    "class": task.task_class,
                    "ok": False,
                    "ms": 0.0,
                    "attempt": task.attempt,
                    "output": "deadline exceeded",
                })
                Metrics.inc("taskqueue.expired", tags={"kind": task.kind, "class": task.task_class})
                Metrics.gauge("taskqueue.size", float(self._queue.qsize()))
                log_event("taskqueue_expired", {
                    "task_id": task.task_id,
                    "kind": task.kind,
                    "class": task.task_class,
                    "attempt": task.attempt,
                }, source="task_queue")
                self._queue.task_done()
                continue

            started = time.time()
            ok = True
            output = ""
            try:
                if task.task_class == "heavy":
                    offloaded = self._try_preemptive_offload(task)
                    if offloaded is not None:
                        ok, output = offloaded
                        duration_ms = (time.time() - started) * 1000.0
                        self._durations_ms.append(duration_ms)
                        Metrics.observe("taskqueue.duration_ms", duration_ms, tags={"kind": task.kind, "class": task.task_class})
                        if ok:
                            self._processed += 1
                            self._offloaded += 1
                            Metrics.inc("taskqueue.offloaded", tags={"kind": task.kind, "class": task.task_class})
                        else:
                            self._failed += 1
                            Metrics.inc("taskqueue.failed", tags={"kind": task.kind, "class": task.task_class})
                        self._results.appendleft({
                            "id": task.task_id,
                            "kind": task.kind,
                            "class": task.task_class,
                            "ok": ok,
                            "ms": round(duration_ms, 1),
                            "attempt": task.attempt,
                            "output": output[:400],
                        })
                        Metrics.gauge("taskqueue.size", float(self._queue.qsize()))
                        self._queue.task_done()
                        continue

                runner = self._runners.get(task.kind)
                if not runner:
                    raise RuntimeError(f"runner not found for kind={task.kind}")
                result = runner(task)
                output = str(result) if result is not None else ""
            except Exception as e:
                ok = False
                output = str(e)
                log.error("TaskQueue worker#%d task#%d error: %s", worker_id, task.task_id, e)

            duration_ms = (time.time() - started) * 1000.0
            self._durations_ms.append(duration_ms)
            Metrics.observe("taskqueue.duration_ms", duration_ms, tags={"kind": task.kind, "class": task.task_class})
            if ok:
                self._processed += 1
                Metrics.inc("taskqueue.done", tags={"kind": task.kind, "class": task.task_class})
            else:
                if task.attempt < task.max_retries:
                    task.attempt += 1
                    self._retried += 1
                    backoff = (task.backoff_ms / 1000.0) * (2 ** (task.attempt - 1))
                    task.next_run_at = time.time() + min(backoff, 30.0)
                    self._queue.put(task)
                    Metrics.inc("taskqueue.retried", tags={"kind": task.kind, "class": task.task_class})
                    log_event("taskqueue_retried", {
                        "task_id": task.task_id,
                        "kind": task.kind,
                        "class": task.task_class,
                        "attempt": task.attempt,
                        "next_in_sec": round(min(backoff, 30.0), 2),
                    }, source="task_queue")
                    self._queue.task_done()
                    continue

                self._failed += 1
                Metrics.inc("taskqueue.failed", tags={"kind": task.kind, "class": task.task_class})

            self._results.appendleft({
                "id": task.task_id,
                "kind": task.kind,
                "class": task.task_class,
                "ok": ok,
                "ms": round(duration_ms, 1),
                "attempt": task.attempt,
                "output": output[:400],
            })
            Metrics.gauge("taskqueue.size", float(self._queue.qsize()))
            self._queue.task_done()

            now = time.time()
            self._run_idle_learning_cycle(now, force=False)
            self._check_acceptance_backpressure(now)

    def set_workers(self, count: int) -> str:
        target = max(1, min(int(count), 16))
        if target <= len(self._workers):
            self.worker_count = target
            return (
                "ℹ️ Уменьшение workers на лету не применяется немедленно. "
                f"Текущих активных: {len(self._workers)}, целевой: {target}."
            )

        additional = target - len(self._workers)
        self.worker_count = target
        if self._running:
            for idx in range(additional):
                wid = len(self._workers) + 1
                thread = threading.Thread(target=self._worker_loop, args=(wid,), daemon=True)
                self._workers.append(thread)
                thread.start()
        return f"✅ Workers увеличены до {target}."

    def status(self) -> str:
        avg_ms = (sum(self._durations_ms) / len(self._durations_ms)) if self._durations_ms else 0.0
        Metrics.gauge("taskqueue.size", float(self._queue.qsize()))
        class_counts = self._queue_class_counts()
        class_counts_str = ", ".join([f"{k}:{class_counts.get(k, 0)}" for k in self.TASK_CLASSES])
        class_rps = ", ".join([f"{k}:{self._class_rps.get(k, 1)}/s" for k in self.TASK_CLASSES])
        return (
            "🧵 TASK QUEUE STATUS\n"
            f"  Running: {'yes' if self._running else 'no'}\n"
            f"  Workers(active/target): {len(self._workers)}/{self.worker_count}\n"
            f"  Queue size: {self._queue.qsize()}\n"
            f"  Classes queued: {class_counts_str}\n"
            f"  Rate limits: {class_rps}\n"
            f"  Done: {self._processed} | Offloaded: {self._offloaded} | Failed: {self._failed} | Retried: {self._retried} | Expired: {self._expired}\n"
            f"  Avg duration: {avg_ms:.1f} ms"
        )

    def last_results(self, limit: int = 5) -> str:
        rows = list(self._results)[:max(1, min(limit, 20))]
        if not rows:
            return "📭 В очереди пока нет завершённых задач."
        lines = [f"📦 TASK RESULTS ({len(rows)}):"]
        for row in rows:
            icon = "✅" if row["ok"] else "❌"
            lines.append(
                f"  {icon} #{row['id']} {row['kind']}[{row.get('class', 'ai')}] "
                f"{row['ms']}ms attempt={row.get('attempt', 0)}"
            )
            if row["output"]:
                lines.append(f"     → {row['output'][:180]}")
        return "\n".join(lines)

    def _normalize_class(self, value: str) -> str:
        task_class = (value or "").strip().lower()
        if task_class not in self.TASK_CLASSES:
            return "ai"
        return task_class

    def _priority_with_class_bias(self, base_priority: int, task_class: str) -> int:
        clamped = max(1, min(int(base_priority), 10))
        bias = {
            "system": -2,
            "iot": -1,
            "ai": 0,
            "heavy": 2,
        }.get(task_class, 0)
        return max(1, min(clamped + bias, 10))

    def _rate_wait_seconds(self, task_class: str, now: float) -> float:
        bucket = self._class_dispatch_ts.get(task_class)
        if bucket is None:
            return 0.0
        while bucket and (now - bucket[0]) > 1.0:
            bucket.popleft()
        rps = self._class_rps.get(task_class, 1)
        if len(bucket) < rps:
            return 0.0
        return max(0.01, (bucket[0] + 1.0) - now)

    def _mark_dispatched(self, task_class: str, now: float):
        bucket = self._class_dispatch_ts.get(task_class)
        if bucket is None:
            return
        bucket.append(now)

    def _queue_class_counts(self) -> dict[str, int]:
        counts = {name: 0 for name in self.TASK_CLASSES}
        with self._queue.mutex:
            for item in list(self._queue.queue):
                counts[item.task_class] = counts.get(item.task_class, 0) + 1
        return counts

    def _try_preemptive_offload(self, task: TaskEnvelope) -> tuple[bool, str] | None:
        guard = self._heavy_preemptive_guard
        runner = self._heavy_failover_runner
        if not guard or not runner:
            return None
        try:
            should_offload = bool(guard(task))
        except Exception as e:
            log.warning("TaskQueue preemptive guard error: %s", e)
            return None
        if not should_offload:
            return None
        try:
            ok, output = runner(task)
            if ok:
                log_event("taskqueue_offloaded", {
                    "task_id": task.task_id,
                    "kind": task.kind,
                    "class": task.task_class,
                    "attempt": task.attempt,
                }, source="task_queue")
                return True, f"[P2P OFFLOAD] {output}"
            return False, f"[P2P OFFLOAD FAILED] {output}"
        except Exception as e:
            log.warning("TaskQueue preemptive offload runner error: %s", e)
            return None

    def _has_pending_ai_or_heavy(self) -> bool:
        with self._queue.mutex:
            for item in list(self._queue.queue):
                if item.task_class in {"ai", "heavy"}:
                    return True
        return False

    def _run_idle_learning_cycle(self, now: float, force: bool):
        handler = self._idle_learning_handler
        if not handler:
            return
        if not force:
            if self._has_pending_ai_or_heavy():
                return
            if (now - self._last_idle_learning_ts) < self._idle_learning_min_sec:
                return
        try:
            result = handler(force)
            self._last_idle_learning_ts = now
            if result and isinstance(result, tuple) and bool(result[0]):
                Metrics.inc("taskqueue.idle_learning.applied")
                log_event("taskqueue_idle_learning", {
                    "ok": True,
                    "detail": str(result[1])[:180],
                    "forced": bool(force),
                }, source="task_queue")
        except Exception as e:
            log.warning("TaskQueue idle learning error: %s", e)

    def _check_acceptance_backpressure(self, now: float):
        if (now - self._last_backpressure_check_ts) < self._backpressure_check_sec:
            return
        self._last_backpressure_check_ts = now

        snap = get_acceptance_snapshot(window=120)
        rate = float(snap.get("rate", 1.0) or 1.0)
        samples = int(snap.get("samples", 0) or 0)
        Metrics.gauge("taskqueue.acceptance_rate", rate)

        if samples < self._acceptance_samples_min:
            return
        if rate >= self._acceptance_floor:
            return
        if (now - self._last_backpressure_action_ts) < 30:
            return

        current_ai_rps = int(self._class_rps.get("ai", 1) or 1)
        reduced_ai_rps = max(1, int(round(current_ai_rps * 0.7)))
        if reduced_ai_rps >= current_ai_rps and current_ai_rps > 1:
            reduced_ai_rps = current_ai_rps - 1

        self._class_rps["ai"] = max(1, reduced_ai_rps)
        os.environ["ARGOS_TASK_RPS_AI"] = str(self._class_rps["ai"])
        self._last_backpressure_action_ts = now
        Metrics.inc("taskqueue.backpressure.applied")
        log_event("taskqueue_backpressure", {
            "reason": "acceptance_rate_low",
            "acceptance_rate": round(rate, 4),
            "samples": samples,
            "old_ai_rps": current_ai_rps,
            "new_ai_rps": self._class_rps["ai"],
        }, source="task_queue")

        self._run_idle_learning_cycle(now, force=True)
