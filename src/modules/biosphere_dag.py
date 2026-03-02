"""
biosphere_dag.py — BiosphereDAG
DAG-контроллер автоматического управления биосферой.
Использует networkx для топологической сортировки графа задач.
Поддерживает: incubator, aquarium, terrarium, greenhouse, generic.
"""

import time
import threading
from typing import Dict, Any, List, Callable, Optional
from src.argos_logger import get_logger

log = get_logger("argos.biosphere_dag")

# networkx — optional
try:
    import networkx as nx
    NX_OK = True
except ImportError:
    nx = None
    NX_OK = False


class BiosphereDAG:
    """
    DAG-движок для автоматического контроля биосферы.

    Шаги:
    1. **read_sensors** — считать все датчики
    2. **evaluate_temp** — сравнить температуру с целевой
    3. **evaluate_humidity** — сравнить влажность с целевой
    4. **evaluate_extras** — дополнительные метрики (pH, CO2, UVI…)
    5. **execute_actions** — выполнить Tool Calling (toggle актуаторов)

    Граф автоматически строится для выбранного environment.
    """

    # Целевые значения по умолчанию для каждого типа среды
    TARGETS = {
        "incubator":  {"temp": 37.5, "humidity": 65.0, "co2_max": 1500},
        "aquarium":   {"temp": 25.0, "ph_min": 6.5, "ph_max": 7.5, "ammonia_max": 0.05},
        "terrarium":  {"temp": 28.0, "humidity": 70.0, "uvi_min": 2.0},
        "greenhouse": {"temp": 24.0, "humidity": 55.0, "soil_min": 25.0},
        "generic":    {"temp": 22.0, "humidity": 45.0},
    }

    def __init__(self, tools=None, environment: str = "generic",
                 targets: Optional[Dict[str, float]] = None):
        """
        Args:
            tools: экземпляр BiosphereTools (или None — создаст свой)
            environment: тип среды
            targets: переопределение целевых значений
        """
        # Lazy import чтобы не зависеть от порядка файлов
        if tools is None:
            from src.modules.biosphere_tools import BiosphereTools
            tools = BiosphereTools(environment=environment)

        self.tools = tools
        self.environment = environment
        self.targets = dict(self.TARGETS.get(environment, self.TARGETS["generic"]))
        if targets:
            self.targets.update(targets)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval_sec: float = 30.0
        self._cycle_count: int = 0
        self._last_result: str = ""
        self._lock = threading.Lock()

        # Строим DAG
        self.dag = None
        self._node_actions: Dict[str, Callable] = {}
        self._build_graph()

        log.info("BiosphereDAG: env=%s, targets=%s, nx=%s",
                 environment, self.targets, "OK" if NX_OK else "fallback")

    # ── ГРАФ ──────────────────────────────────────────────

    def _build_graph(self):
        """Строим DAG. Если networkx нет — используем ручной порядок."""
        nodes = [
            ("read_sensors", self._step_read_sensors),
            ("evaluate_temp", self._step_evaluate_temp),
            ("evaluate_humidity", self._step_evaluate_humidity),
            ("evaluate_extras", self._step_evaluate_extras),
            ("execute_actions", self._step_execute_actions),
        ]
        edges = [
            ("read_sensors", "evaluate_temp"),
            ("read_sensors", "evaluate_humidity"),
            ("read_sensors", "evaluate_extras"),
            ("evaluate_temp", "execute_actions"),
            ("evaluate_humidity", "execute_actions"),
            ("evaluate_extras", "execute_actions"),
        ]

        self._node_actions = {name: fn for name, fn in nodes}

        if NX_OK:
            self.dag = nx.DiGraph()
            for name, fn in nodes:
                self.dag.add_node(name, action=fn)
            self.dag.add_edges_from(edges)
        else:
            # Fallback: фиксированный порядок
            self.dag = None

    def _topo_order(self) -> List[str]:
        """Возвращает топологический порядок узлов."""
        if self.dag is not None and NX_OK:
            return list(nx.topological_sort(self.dag))
        # fallback
        return ["read_sensors", "evaluate_temp", "evaluate_humidity",
                "evaluate_extras", "execute_actions"]

    # ── ШАГИ ──────────────────────────────────────────────

    def _step_read_sensors(self, ctx: dict):
        """Шаг 1: опрос всех датчиков."""
        readings = self.tools.read_all_sensors()
        for r in readings:
            ctx["sensors"][r.sensor_type.value] = r.value
        ctx["_readings"] = readings

    def _step_evaluate_temp(self, ctx: dict):
        """Шаг 2a: анализ температуры."""
        current = ctx["sensors"].get("temperature")
        target = self.targets.get("temp")
        if current is None or target is None:
            return
        delta = current - target
        if delta < -1.0:
            ctx["actions"].append(("heater", True, f"Температура {current:.1f}°C < {target}°C → обогрев ON"))
        elif delta > 1.0:
            ctx["actions"].append(("heater", False, f"Температура {current:.1f}°C > {target}°C → обогрев OFF"))
            ctx["actions"].append(("fan", True, f"Температура {current:.1f}°C > {target}°C → вентиляция ON"))
        else:
            ctx["log"].append(f"  Температура {current:.1f}°C — в норме.")

    def _step_evaluate_humidity(self, ctx: dict):
        """Шаг 2b: анализ влажности."""
        current = ctx["sensors"].get("humidity")
        target = self.targets.get("humidity")
        if current is None or target is None:
            return
        delta = current - target
        if delta < -5.0:
            act = "humidifier" if "humidifier" in self.tools.actuators else "pump"
            ctx["actions"].append((act, True, f"Влажность {current:.1f}% < {target}% → {act} ON"))
        elif delta > 5.0:
            ctx["actions"].append(("fan", True, f"Влажность {current:.1f}% > {target}% → вентиляция ON"))
        else:
            ctx["log"].append(f"  Влажность {current:.1f}% — в норме.")

    def _step_evaluate_extras(self, ctx: dict):
        """Шаг 2c: дополнительные метрики (pH, CO2, UVI, soil…)."""
        sensors = ctx["sensors"]

        # pH (аквариум)
        ph = sensors.get("ph")
        if ph is not None:
            ph_min = self.targets.get("ph_min", 6.5)
            ph_max = self.targets.get("ph_max", 7.5)
            if ph < ph_min:
                ctx["log"].append(f"  ⚠️ pH {ph:.2f} < {ph_min} — требуется коррекция!")
            elif ph > ph_max:
                ctx["log"].append(f"  ⚠️ pH {ph:.2f} > {ph_max} — требуется коррекция!")

        # CO2 (инкубатор, теплица)
        co2 = sensors.get("co2")
        co2_max = self.targets.get("co2_max")
        if co2 is not None and co2_max is not None:
            if co2 > co2_max:
                ctx["actions"].append(("fan", True, f"CO2 {co2:.0f}ppm > {co2_max} → вентиляция ON"))

        # Soil moisture (теплица)
        soil = sensors.get("soil_moisture")
        soil_min = self.targets.get("soil_min")
        if soil is not None and soil_min is not None:
            if soil < soil_min:
                ctx["actions"].append(("irrigation", True,
                                       f"Влажность почвы {soil:.1f}% < {soil_min}% → полив ON"))

        # UVI (террариум)
        uvi = sensors.get("uvi")
        uvi_min = self.targets.get("uvi_min")
        if uvi is not None and uvi_min is not None:
            if uvi < uvi_min:
                ctx["log"].append(f"  ⚠️ UVI {uvi:.1f} < {uvi_min} — UV-лампа может потребовать замены")

        # Ammonia (аквариум)
        nh3 = sensors.get("ammonia")
        nh3_max = self.targets.get("ammonia_max")
        if nh3 is not None and nh3_max is not None:
            if nh3 > nh3_max:
                ctx["actions"].append(("pump", True,
                                       f"Аммиак {nh3:.3f}ppm > {nh3_max} → фильтрация ON"))

    def _step_execute_actions(self, ctx: dict):
        """Шаг 3: выполнение действий (Tool Calling)."""
        if not ctx["actions"]:
            ctx["log"].append("  ✅ Система стабильна. Действия не требуются.")
            return
        for actuator, state, reason in ctx["actions"]:
            try:
                result = self.tools.toggle(actuator, state)
                ctx["log"].append(f"  {result} — {reason}")
            except Exception as e:
                ctx["log"].append(f"  ❌ Ошибка {actuator}: {e}")

    # ── ЦИКЛ ──────────────────────────────────────────────

    def run_cycle(self) -> str:
        """
        Запуск одного цикла контроля биосферы по DAG.
        Возвращает текстовый отчёт.
        """
        ctx: Dict[str, Any] = {
            "sensors": {},
            "actions": [],
            "log": [],
            "_readings": [],
        }

        header = f"=== ЦИКЛ КОНТРОЛЯ БИОСФЕРЫ [{self.environment.upper()}] ==="
        ctx["log"].append(header)

        for node_name in self._topo_order():
            fn = self._node_actions.get(node_name)
            if fn:
                try:
                    fn(ctx)
                except Exception as e:
                    ctx["log"].append(f"  ❌ Ошибка в {node_name}: {e}")
                    log.error("BiosphereDAG node %s: %s", node_name, e)

        ctx["log"].append("=== ЦИКЛ ЗАВЕРШЁН ===")
        result = "\n".join(ctx["log"])

        with self._lock:
            self._cycle_count += 1
            self._last_result = result

        log.info("BiosphereDAG cycle #%d complete, actions=%d",
                 self._cycle_count, len(ctx["actions"]))
        return result

    # ── АВТОЦИКЛ ──────────────────────────────────────────

    def start(self, interval_sec: float = 30.0) -> str:
        """Запускает автоцикл в фоне."""
        if self._running:
            return "🌿 BiosphereDAG: уже запущен."
        self._interval_sec = interval_sec
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="biosphere-dag")
        self._thread.start()
        return f"🌿 BiosphereDAG: автоцикл запущен (каждые {interval_sec}с)."

    def stop(self) -> str:
        """Останавливает автоцикл."""
        if not self._running:
            return "🌿 BiosphereDAG: не запущен."
        self._running = False
        return "🌿 BiosphereDAG: остановлен."

    def _loop(self):
        while self._running:
            try:
                self.run_cycle()
            except Exception as e:
                log.error("BiosphereDAG loop: %s", e)
            time.sleep(self._interval_sec)

    # ── НАСТРОЙКА ─────────────────────────────────────────

    def set_target(self, key: str, value: float) -> str:
        """Устанавливает целевое значение."""
        self.targets[key] = value
        return f"🌿 Целевое значение {key} = {value}"

    def get_targets(self) -> dict:
        return dict(self.targets)

    # ── СТАТУС ────────────────────────────────────────────

    def status(self) -> str:
        lines = [f"🌿 BIOSPHERE DAG [{self.environment.upper()}]:"]
        lines.append(f"  Циклов: {self._cycle_count}")
        lines.append(f"  Автоцикл: {'ON' if self._running else 'OFF'}")
        if self._running:
            lines.append(f"  Интервал: {self._interval_sec}с")
        lines.append(f"  networkx: {'OK' if NX_OK else 'fallback'}")
        lines.append(f"  Узлов в DAG: {len(self._node_actions)}")
        lines.append("  Целевые значения:")
        for k, v in self.targets.items():
            lines.append(f"    {k}: {v}")
        # Текущие показания
        tools_status = self.tools.status()
        lines.append("")
        lines.append(tools_status)
        return "\n".join(lines)

    def get_last_result(self) -> str:
        with self._lock:
            return self._last_result or "Циклов ещё не было."


# ── Singleton ─────────────────────────────────────────────

_instances: Dict[str, BiosphereDAG] = {}
_inst_lock = threading.Lock()


def get_biosphere_dag(environment: str = "generic", **kwargs) -> BiosphereDAG:
    """Возвращает singleton BiosphereDAG для данного environment."""
    global _instances
    with _inst_lock:
        if environment not in _instances:
            _instances[environment] = BiosphereDAG(environment=environment, **kwargs)
        return _instances[environment]
