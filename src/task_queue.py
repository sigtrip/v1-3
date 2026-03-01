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


@dataclass(order=True)
class TaskEnvelope:
    priority: int
    created_at: float
    task_id: int = field(compare=False)
    kind: str = field(compare=False)
    payload: dict = field(compare=False)


class TaskQueueManager:
    def __init__(self, worker_count: int = 2):
        self._queue: queue.PriorityQueue[TaskEnvelope] = queue.PriorityQueue()
        self._lock = threading.Lock()
        self._running = False
        self._workers: list[threading.Thread] = []
        self._next_id = 1
        self._runners: dict[str, Callable[[TaskEnvelope], Any]] = {}

        self._processed = 0
        self._failed = 0
        self._durations_ms: deque[float] = deque(maxlen=300)
        self._results: deque[dict] = deque(maxlen=100)

        env_workers = int(os.getenv("ARGOS_TASK_WORKERS", str(worker_count)) or str(worker_count))
        self.worker_count = max(1, min(env_workers, 16))

    def register_runner(self, kind: str, runner: Callable[[TaskEnvelope], Any]):
        if not kind or not callable(runner):
            return
        self._runners[kind] = runner

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
        with self._lock:
            task_id = self._next_id
            self._next_id += 1
        env = TaskEnvelope(
            priority=max(1, min(int(priority), 10)),
            created_at=time.time(),
            task_id=task_id,
            kind=kind,
            payload=payload or {},
        )
        self._queue.put(env)
        return task_id

    def _worker_loop(self, worker_id: int):
        while self._running:
            try:
                task = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            started = time.time()
            ok = True
            output = ""
            try:
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
            if ok:
                self._processed += 1
            else:
                self._failed += 1

            self._results.appendleft({
                "id": task.task_id,
                "kind": task.kind,
                "ok": ok,
                "ms": round(duration_ms, 1),
                "output": output[:400],
            })
            self._queue.task_done()

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
        return (
            "🧵 TASK QUEUE STATUS\n"
            f"  Running: {'yes' if self._running else 'no'}\n"
            f"  Workers(active/target): {len(self._workers)}/{self.worker_count}\n"
            f"  Queue size: {self._queue.qsize()}\n"
            f"  Done: {self._processed} | Failed: {self._failed}\n"
            f"  Avg duration: {avg_ms:.1f} ms"
        )

    def last_results(self, limit: int = 5) -> str:
        rows = list(self._results)[:max(1, min(limit, 20))]
        if not rows:
            return "📭 В очереди пока нет завершённых задач."
        lines = [f"📦 TASK RESULTS ({len(rows)}):"]
        for row in rows:
            icon = "✅" if row["ok"] else "❌"
            lines.append(f"  {icon} #{row['id']} {row['kind']} {row['ms']}ms")
            if row["output"]:
                lines.append(f"     → {row['output'][:180]}")
        return "\n".join(lines)
