"""
container_isolation.py — LXD / Docker Isolation
    Каждый модуль-дополнение может работать в изолированном контейнере.
    При компрометации одного модуля система остаётся целой.

    Поддержка:
    - Docker (приоритет): через docker CLI / docker SDK
    - LXD: через lxc CLI
    - Мониторинг состояния контейнеров
    - Автоочистка зависших / утёкших контейнеров
    - Сетевая изоляция (--network=none / bridge)

    ⚠ Запуск контейнеров требует прав Docker-группы или root.
"""
import os
import re
import time
import json
import shutil
import subprocess
import threading
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field, asdict

from src.argos_logger import get_logger

log = get_logger("argos.isolation")


# ── Enums / Dataclasses ─────────────────────────────────
class Runtime(Enum):
    DOCKER = "docker"
    LXD = "lxd"
    NONE = "none"


class ContainerState(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    CREATING = "creating"
    ERROR = "error"
    UNKNOWN = "unknown"


class NetworkMode(Enum):
    NONE = "none"           # полная изоляция
    BRIDGE = "bridge"       # доступ через bridge
    HOST = "host"           # общая сеть (небезопасно)


@dataclass
class ContainerInfo:
    """Метаинформация о контейнере."""
    name: str
    module: str                                # имя модуля Аргоса
    runtime: str = "docker"
    image: str = "python:3.12-slim"
    state: str = "unknown"
    network: str = "none"
    container_id: str = ""
    created_at: float = field(default_factory=time.time)
    cpu_limit: str = "0.5"                     # --cpus
    mem_limit: str = "256m"                    # --memory
    auto_restart: bool = True
    ports: Dict[str, str] = field(default_factory=dict)
    volumes: Dict[str, str] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    last_health: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class ContainerIsolation:
    """
    Менеджер контейнерной изоляции модулей.

    - auto-detect runtime (Docker > LXD)
    - запуск / остановка / перезапуск модулей в контейнерах
    - сетевая изоляция по умолчанию (--network=none)
    - лимиты CPU/RAM
    - watchdog: проверка состояния + автоочистка
    """

    LABEL = "argos.module"  # Docker label для фильтрации

    def __init__(self):
        self._lock = threading.Lock()
        self._runtime = self._detect_runtime()
        self._containers: Dict[str, ContainerInfo] = {}
        self._history: deque = deque(maxlen=100)
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_running = False
        self._watchdog_interval = int(os.getenv("ARGOS_ISO_WATCHDOG_SEC", "30"))
        self._default_image = os.getenv("ARGOS_ISO_IMAGE", "python:3.12-slim")
        self._default_network = NetworkMode(
            os.getenv("ARGOS_ISO_NETWORK", "none").strip().lower()
        ) if os.getenv("ARGOS_ISO_NETWORK") else NetworkMode.NONE
        log.info("ContainerIsolation: runtime=%s", self._runtime.value)

    # ── Детекция runtime ─────────────────────────────────

    @staticmethod
    def _detect_runtime() -> Runtime:
        """Определить доступный runtime."""
        if shutil.which("docker"):
            try:
                r = subprocess.run(["docker", "info"], capture_output=True,
                                   timeout=5, text=True)
                if r.returncode == 0:
                    return Runtime.DOCKER
            except Exception:
                pass
        if shutil.which("lxc"):
            try:
                r = subprocess.run(["lxc", "list", "--format=json"],
                                   capture_output=True, timeout=5, text=True)
                if r.returncode == 0:
                    return Runtime.LXD
            except Exception:
                pass
        return Runtime.NONE

    # ── Публичный API ────────────────────────────────────

    def launch(self, module: str, *,
               image: Optional[str] = None,
               network: Optional[str] = None,
               cpu: str = "0.5",
               mem: str = "256m",
               ports: Optional[Dict[str, str]] = None,
               volumes: Optional[Dict[str, str]] = None,
               env: Optional[Dict[str, str]] = None,
               cmd: Optional[str] = None) -> str:
        """Запустить модуль в контейнере."""
        if self._runtime == Runtime.NONE:
            return "❌ Docker / LXD не обнаружен."

        name = f"argos-{module.replace('/', '-').replace('.', '-')}"
        with self._lock:
            if name in self._containers:
                c = self._containers[name]
                if c.state == ContainerState.RUNNING.value:
                    return f"ℹ️ Контейнер '{name}' уже запущен."

        img = image or self._default_image
        net = network or self._default_network.value

        info = ContainerInfo(
            name=name,
            module=module,
            runtime=self._runtime.value,
            image=img,
            network=net,
            cpu_limit=cpu,
            mem_limit=mem,
            ports=ports or {},
            volumes=volumes or {},
            env=env or {},
        )

        try:
            if self._runtime == Runtime.DOCKER:
                cid = self._docker_run(info, cmd)
                info.container_id = cid
                info.state = ContainerState.RUNNING.value
            elif self._runtime == Runtime.LXD:
                self._lxd_launch(info, cmd)
                info.state = ContainerState.RUNNING.value
        except Exception as exc:
            info.state = ContainerState.ERROR.value
            info.errors.append(str(exc)[:200])
            log.error("launch %s: %s", name, exc)
            with self._lock:
                self._containers[name] = info
            return f"❌ Ошибка запуска '{name}': {exc}"

        with self._lock:
            self._containers[name] = info
            self._history.append({
                "ts": time.time(), "action": "launch",
                "name": name, "module": module, "image": img,
            })

        log.info("Container '%s' launched (runtime=%s)", name, self._runtime.value)
        return f"✅ Контейнер '{name}' запущен ({self._runtime.value}, {img}, net={net})"

    def stop(self, name: str) -> str:
        """Остановить контейнер."""
        with self._lock:
            info = self._containers.get(name)
        if not info:
            return f"❌ Контейнер '{name}' не найден."

        try:
            if self._runtime == Runtime.DOCKER:
                subprocess.run(["docker", "stop", name],
                               capture_output=True, timeout=30, text=True, check=True)
            elif self._runtime == Runtime.LXD:
                subprocess.run(["lxc", "stop", name],
                               capture_output=True, timeout=30, text=True, check=True)
            with self._lock:
                info.state = ContainerState.STOPPED.value
                self._history.append({"ts": time.time(), "action": "stop", "name": name})
            return f"✅ Контейнер '{name}' остановлен."
        except Exception as exc:
            return f"❌ Ошибка остановки '{name}': {exc}"

    def restart(self, name: str) -> str:
        """Перезапустить контейнер."""
        with self._lock:
            info = self._containers.get(name)
        if not info:
            return f"❌ Контейнер '{name}' не найден."
        try:
            if self._runtime == Runtime.DOCKER:
                subprocess.run(["docker", "restart", name],
                               capture_output=True, timeout=30, text=True, check=True)
            elif self._runtime == Runtime.LXD:
                subprocess.run(["lxc", "restart", name],
                               capture_output=True, timeout=30, text=True, check=True)
            with self._lock:
                info.state = ContainerState.RUNNING.value
                self._history.append({"ts": time.time(), "action": "restart", "name": name})
            return f"✅ Контейнер '{name}' перезапущен."
        except Exception as exc:
            return f"❌ Ошибка перезапуска '{name}': {exc}"

    def remove(self, name: str) -> str:
        """Удалить контейнер."""
        self.stop(name)
        try:
            if self._runtime == Runtime.DOCKER:
                subprocess.run(["docker", "rm", "-f", name],
                               capture_output=True, timeout=15, text=True)
            elif self._runtime == Runtime.LXD:
                subprocess.run(["lxc", "delete", name, "--force"],
                               capture_output=True, timeout=15, text=True)
            with self._lock:
                self._containers.pop(name, None)
                self._history.append({"ts": time.time(), "action": "remove", "name": name})
            return f"✅ Контейнер '{name}' удалён."
        except Exception as exc:
            return f"❌ Ошибка удаления '{name}': {exc}"

    def logs(self, name: str, tail: int = 50) -> str:
        """Получить последние логи контейнера."""
        if self._runtime == Runtime.DOCKER:
            try:
                r = subprocess.run(
                    ["docker", "logs", "--tail", str(tail), name],
                    capture_output=True, timeout=10, text=True)
                return r.stdout[-4000:] if r.stdout else "(пусто)"
            except Exception as exc:
                return f"❌ {exc}"
        return "❌ Логи доступны только для Docker."

    def exec_cmd(self, name: str, command: str) -> str:
        """Выполнить команду внутри контейнера."""
        if self._runtime == Runtime.DOCKER:
            try:
                r = subprocess.run(
                    ["docker", "exec", name] + command.split(),
                    capture_output=True, timeout=30, text=True)
                out = (r.stdout + r.stderr)[:4000]
                return out or "(пусто)"
            except Exception as exc:
                return f"❌ {exc}"
        elif self._runtime == Runtime.LXD:
            try:
                r = subprocess.run(
                    ["lxc", "exec", name, "--"] + command.split(),
                    capture_output=True, timeout=30, text=True)
                return (r.stdout + r.stderr)[:4000] or "(пусто)"
            except Exception as exc:
                return f"❌ {exc}"
        return "❌ Runtime недоступен."

    def list_containers(self) -> str:
        """Список всех контейнеров Аргоса."""
        self._refresh_states()
        with self._lock:
            containers = list(self._containers.values())
        if not containers:
            return "📦 Нет активных контейнеров.\n  Runtime: " + self._runtime.value
        lines = [f"📦 КОНТЕЙНЕРЫ АРГОСА ({self._runtime.value}):"]
        for c in containers:
            state_icon = {
                "running": "🟢", "stopped": "🔴", "paused": "🟡",
                "error": "❌", "creating": "🔵",
            }.get(c.state, "⚪")
            lines.append(
                f"  {state_icon} {c.name} — {c.module} "
                f"({c.image}, CPU={c.cpu_limit}, MEM={c.mem_limit}, net={c.network})"
            )
        return "\n".join(lines)

    def cleanup(self) -> str:
        """Удалить все остановленные / error контейнеры."""
        removed = 0
        with self._lock:
            to_remove = [
                name for name, c in self._containers.items()
                if c.state in (ContainerState.STOPPED.value, ContainerState.ERROR.value)
            ]
        for name in to_remove:
            self.remove(name)
            removed += 1
        return f"🧹 Очищено контейнеров: {removed}"

    def get_status(self) -> dict:
        """Статус подсистемы."""
        self._refresh_states()
        with self._lock:
            running = sum(1 for c in self._containers.values()
                          if c.state == ContainerState.RUNNING.value)
            total = len(self._containers)
        return {
            "runtime": self._runtime.value,
            "containers_total": total,
            "containers_running": running,
            "watchdog_active": self._watchdog_running,
            "default_network": self._default_network.value,
            "default_image": self._default_image,
        }

    def status(self) -> str:
        """Человекочитаемый статус."""
        s = self.get_status()
        lines = [
            "📦 CONTAINER ISOLATION",
            f"  Runtime: {s['runtime']}",
            f"  Контейнеров: {s['containers_running']}/{s['containers_total']} running",
            f"  Watchdog: {'✅ вкл' if s['watchdog_active'] else '⚪ выкл'}",
            f"  Сеть: {s['default_network']}",
            f"  Образ: {s['default_image']}",
        ]
        return "\n".join(lines)

    def history_text(self, limit: int = 20) -> str:
        """История операций."""
        records = list(self._history)[-limit:]
        if not records:
            return "📋 История пуста."
        lines = ["📋 ИСТОРИЯ КОНТЕЙНЕРОВ:"]
        for r in records:
            dt = time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))
            lines.append(f"  {dt} {r['action']} — {r['name']}")
        return "\n".join(lines)

    # ── Watchdog ─────────────────────────────────────────

    def start_watchdog(self) -> str:
        """Запустить фоновый watchdog."""
        if self._watchdog_running:
            return "ℹ️ Watchdog уже запущен."
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="argos-iso-watchdog")
        self._watchdog_thread.start()
        return "✅ Watchdog контейнеров запущен."

    def stop_watchdog(self) -> str:
        """Остановить watchdog."""
        self._watchdog_running = False
        return "✅ Watchdog остановлен."

    def _watchdog_loop(self):
        while self._watchdog_running:
            try:
                self._refresh_states()
                # Автоперезапуск рухнувших контейнеров
                with self._lock:
                    crashed = [
                        name for name, c in self._containers.items()
                        if c.state in (ContainerState.STOPPED.value, ContainerState.ERROR.value)
                        and c.auto_restart
                    ]
                for name in crashed:
                    log.warning("Watchdog: auto-restart %s", name)
                    self.restart(name)
            except Exception as exc:
                log.error("watchdog: %s", exc)
            time.sleep(self._watchdog_interval)

    # ── Внутренние методы ────────────────────────────────

    def _refresh_states(self):
        """Обновить состояния контейнеров из runtime."""
        if self._runtime == Runtime.DOCKER:
            self._docker_refresh()
        elif self._runtime == Runtime.LXD:
            self._lxd_refresh()

    def _docker_refresh(self):
        try:
            r = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"label={self.LABEL}",
                 "--format", "{{.Names}}|{{.State}}|{{.ID}}"],
                capture_output=True, timeout=10, text=True)
            if r.returncode != 0:
                return
            live = {}
            for line in r.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|")
                if len(parts) >= 3:
                    live[parts[0]] = (parts[1], parts[2])
            with self._lock:
                for name, info in self._containers.items():
                    if name in live:
                        state_str, cid = live[name]
                        info.state = self._docker_state_map(state_str)
                        info.container_id = cid
                        info.last_health = time.time()
        except Exception as exc:
            log.debug("docker refresh: %s", exc)

    def _lxd_refresh(self):
        try:
            r = subprocess.run(
                ["lxc", "list", "--format=json"],
                capture_output=True, timeout=10, text=True)
            if r.returncode != 0:
                return
            data = json.loads(r.stdout)
            live = {}
            for c in data:
                live[c.get("name", "")] = c.get("status", "").lower()
            with self._lock:
                for name, info in self._containers.items():
                    if name in live:
                        info.state = live[name]
                        info.last_health = time.time()
        except Exception as exc:
            log.debug("lxd refresh: %s", exc)

    def _docker_run(self, info: ContainerInfo, cmd: Optional[str]) -> str:
        """Запуск контейнера через docker CLI."""
        args = [
            "docker", "run", "-d",
            "--name", info.name,
            "--label", f"{self.LABEL}={info.module}",
            "--cpus", info.cpu_limit,
            "--memory", info.mem_limit,
            "--restart", "unless-stopped" if info.auto_restart else "no",
            "--network", info.network,
        ]
        for hp, cp in info.ports.items():
            args.extend(["-p", f"{hp}:{cp}"])
        for hv, cv in info.volumes.items():
            args.extend(["-v", f"{hv}:{cv}"])
        for k, v in info.env.items():
            args.extend(["-e", f"{k}={v}"])
        args.append(info.image)
        if cmd:
            args.extend(cmd.split())

        r = subprocess.run(args, capture_output=True, timeout=60, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:300])
        return r.stdout.strip()[:12]  # container ID

    def _lxd_launch(self, info: ContainerInfo, cmd: Optional[str]) -> None:
        """Запуск через lxc."""
        r = subprocess.run(
            ["lxc", "launch", info.image, info.name],
            capture_output=True, timeout=60, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:300])
        # Применить лимиты
        subprocess.run(
            ["lxc", "config", "set", info.name,
             f"limits.cpu={info.cpu_limit}", f"limits.memory={info.mem_limit}"],
            capture_output=True, timeout=10, text=True)

    @staticmethod
    def _docker_state_map(state: str) -> str:
        state = state.lower()
        if state in ("running", "up"):
            return ContainerState.RUNNING.value
        if state in ("exited", "dead"):
            return ContainerState.STOPPED.value
        if state == "paused":
            return ContainerState.PAUSED.value
        if state == "created":
            return ContainerState.CREATING.value
        return ContainerState.UNKNOWN.value

    def shutdown(self):
        """Остановить все контейнеры и watchdog."""
        self._watchdog_running = False
        with self._lock:
            names = list(self._containers.keys())
        for name in names:
            self.stop(name)
        log.info("ContainerIsolation shutdown complete.")


# ── Singleton ────────────────────────────────────────────
_instance: Optional[ContainerIsolation] = None
_instance_lock = threading.Lock()


def get_container_isolation() -> ContainerIsolation:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ContainerIsolation()
    return _instance
