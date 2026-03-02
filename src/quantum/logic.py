import os
import random
import math
import time
import threading
import psutil
import requests
from datetime import datetime

try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_ibm_runtime import QiskitRuntimeService
    IBM_QISKIT_OK = True
except Exception:
    QuantumCircuit = None
    transpile = None
    QiskitRuntimeService = None
    IBM_QISKIT_OK = False

class BayesianNode:
    def __init__(self, name, parents=None, cpt=None):
        self.name = name
        self.parents = parents or []
        self.cpt = cpt or {}  # Conditional Probability Table

    def get_probability(self, parent_vals):
        key = tuple([parent_vals[p] for p in self.parents])
        return self.cpt.get(key, 0.5)

class ArgosQuantum:
    """
    Вероятностная модель состояний Аргоса на основе упрощенных Байесовских сетей.
    Вместо if/else — матрица вероятностей, зависящая от факторов среды.
    """
    def __init__(self):
        self.states = ["Analytic", "Creative", "Protective", "Unstable", "All-Seeing"]
        self._lock = threading.Lock()
        self._forced_state = None
        self._forced_until = 0.0
        self._external = {"cpu": None, "ram": None, "temp": None, "until": 0.0}
        
        # Факты о среде (Evidence)
        self.evidence = {
            "high_load": False,    # CPU > 70%
            "high_ram": False,     # RAM > 80%
            "night_time": False,   # 22:00 - 06:00
            "high_temp": False,    # Temperature > 75C
            "thermal_risk": False,
            "cpu": 0.0,
            "ram": 0.0,
            "temp": None,
            "user_active": True    # Активность пользователя (заглушка)
        }

    def force_state(self, state: str, ttl_seconds: int = 20):
        if state not in self.states:
            return
        with self._lock:
            self._forced_state = state
            self._forced_until = time.time() + max(1, int(ttl_seconds))

    def set_external_telemetry(self, cpu: float | None = None, ram: float | None = None,
                               temp: float | None = None, ttl_seconds: int = 15):
        with self._lock:
            self._external = {
                "cpu": cpu,
                "ram": ram,
                "temp": temp,
                "until": time.time() + max(1, int(ttl_seconds)),
            }

    def _read_temp_c(self) -> float | None:
        try:
            sensors = psutil.sensors_temperatures() or {}
            vals = []
            for entries in sensors.values():
                for entry in entries:
                    cur = getattr(entry, "current", None)
                    if isinstance(cur, (int, float)):
                        vals.append(float(cur))
            return max(vals) if vals else None
        except Exception:
            return None

    def _effective_metric(self, key: str, sampler):
        with self._lock:
            ext = dict(self._external)
        if ext.get("until", 0.0) > time.time() and ext.get(key) is not None:
            return ext.get(key)
        return sampler()
        
    def _update_evidence(self):
        cpu = self._effective_metric("cpu", lambda: psutil.cpu_percent(interval=0.15))
        ram = self._effective_metric("ram", lambda: psutil.virtual_memory().percent)
        temp = self._effective_metric("temp", self._read_temp_c)

        self.evidence["cpu"] = float(cpu or 0.0)
        self.evidence["ram"] = float(ram or 0.0)
        self.evidence["temp"] = float(temp) if isinstance(temp, (int, float)) else None
        self.evidence["high_load"] = self.evidence["cpu"] > 70
        self.evidence["high_ram"] = self.evidence["ram"] > 80
        self.evidence["high_temp"] = (self.evidence["temp"] or 0.0) > 75 if self.evidence["temp"] is not None else False
        self.evidence["thermal_risk"] = (self.evidence["temp"] or 0.0) > 83 if self.evidence["temp"] is not None else False
            
        hour = datetime.now().hour
        self.evidence["night_time"] = (hour >= 22 or hour < 6)
        
        # TODO: Реальная проверка активности пользователя (клавиатура/мышь)
        
    def infer_state(self):
        """
        Рассчитывает наиболее вероятное состояние системы на основе Bayesian Inference.
        P(State | Evidence)
        """
        self._update_evidence()

        with self._lock:
            forced_state = self._forced_state if self._forced_until > time.time() else None

        if forced_state:
            probs = {s: 0.0 for s in self.states}
            probs[forced_state] = 1.0
            return {
                "state": forced_state,
                "vector": [probs[s] for s in self.states],
                "evidence": self.evidence,
                "probabilities": probs,
            }
        
        probs = {s: 0.1 for s in self.states} # Начнем с априорной вероятности (uniform + noise)
        
        # Таблицы условных вероятностей (hardcoded simplified CPT)
        # 1. Если высокая нагрузка -> P(Protective)++, P(Analytic)+
        if self.evidence["high_load"]:
            probs["Protective"] += 0.4
            probs["Analytic"]   += 0.2
            probs["Creative"]   -= 0.1

        if self.evidence["high_ram"]:
            probs["Protective"] += 0.35
            probs["Unstable"]   += 0.15

        if self.evidence["high_temp"]:
            probs["Protective"] += 0.5
            probs["Analytic"]   -= 0.1

        if self.evidence["thermal_risk"]:
            probs["Unstable"] += 1.0
            probs["Protective"] += 0.4
            probs["Creative"] -= 0.2

        if self.evidence["cpu"] > 92 or self.evidence["ram"] > 94:
            probs["Unstable"] += 0.8
            
        # 2. Если ночь -> P(Creative)++, P(All-Seeing)+
        if self.evidence["night_time"]:
            probs["Creative"]   += 0.5
            probs["All-Seeing"] += 0.3
            probs["Analytic"]   -= 0.1
        else:
            probs["Analytic"]   += 0.3 # Днём мы аналитики
            
        # 3. Нормализация
        total = max(sum(probs.values()), 0.0001)
        normalized_probs = {k: round(v/total, 3) for k, v in probs.items()}
        
        # Выбор наиболее вероятного (Max A Posteriori) или сэмплирование
        # Используем взвешенный выбор для "живости"
        states_list = list(normalized_probs.keys())
        weights     = list(normalized_probs.values())
        
        chosen_state = random.choices(states_list, weights=weights, k=1)[0]
        
        return {
            "state": chosen_state,
            "vector": [normalized_probs[s] for s in self.states],
            "evidence": self.evidence,
            "probabilities": normalized_probs
        }

    def generate_state(self):
        # Совместимость со старым API
        # Возвращаем список вероятностей как вектор
        res = self.infer_state()
        vector_list = [res["probabilities"].get(s, 0.0) for s in self.states]
        return {"name": res["state"], "vector": vector_list, "probabilities": res["probabilities"]}

    def _ibm_key(self) -> str:
        return (os.getenv("IBM_QUANTUM_KEY") or os.getenv("IBM_CLOUD_API_KEY") or "").strip()

    def _ibm_channel(self) -> str:
        value = (os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum") or "ibm_quantum").strip().lower()
        if value in {"ibm_cloud", "cloud"}:
            return "ibm_cloud"
        return "ibm_quantum"

    def _ibm_instance(self) -> str:
        return (os.getenv("IBM_QUANTUM_INSTANCE") or "").strip()

    def _ibm_service(self):
        if not IBM_QISKIT_OK:
            return None, "Qiskit Runtime не установлен (pip install qiskit qiskit-ibm-runtime)."

        token = self._ibm_key()
        if not token:
            return None, "IBM_QUANTUM_KEY (или IBM_CLOUD_API_KEY) не найден в .env."

        kwargs = {
            "channel": self._ibm_channel(),
            "token": token,
        }
        instance = self._ibm_instance()
        if instance:
            kwargs["instance"] = instance

        try:
            service = QiskitRuntimeService(**kwargs)
            return service, ""
        except Exception as e:
            return None, f"Ошибка инициализации IBM Runtime: {e}"

    @staticmethod
    def _backend_name(backend) -> str:
        name = getattr(backend, "name", "")
        try:
            return name() if callable(name) else str(name)
        except Exception:
            return str(name)

    def list_ibm_backends(self, limit: int = 10) -> str:
        service, err = self._ibm_service()
        if not service:
            return f"[⚠️] IBM Quantum Runtime недоступен: {err}"

        try:
            backends = service.backends()
            if not backends:
                return "[⚠️] IBM Quantum: backend'ы не найдены."

            items = []
            for backend in backends:
                try:
                    name = self._backend_name(backend)
                    simulator = bool(getattr(backend, "simulator", False))
                    operational = bool(getattr(backend, "operational", True))
                    pending = getattr(backend, "pending_jobs", "?")
                    items.append((name, simulator, operational, pending))
                except Exception:
                    continue

            items.sort(key=lambda x: (not x[2], x[3] if isinstance(x[3], int) else 999999, x[0]))
            head = items[:max(1, int(limit))]

            lines = ["[🌌] IBM Quantum Runtime backend'ы:"]
            for name, simulator, operational, pending in head:
                kind = "SIM" if simulator else "QPU"
                op = "ON" if operational else "OFF"
                lines.append(f"  • {name} [{kind}] op={op} pending={pending}")
            lines.append(f"  Всего backend'ов: {len(items)}")
            return "\n".join(lines)
        except Exception as e:
            return f"[⚠️] Ошибка запроса backend'ов IBM: {e}"

    def run_ibm_bell_test(self, shots: int = 256) -> str:
        service, err = self._ibm_service()
        if not service:
            return f"[⚠️] IBM Quantum Runtime недоступен: {err}"

        try:
            backend_name = (os.getenv("IBM_QUANTUM_BACKEND") or "").strip()
            backend = None

            if backend_name:
                backend = service.backend(backend_name)
            else:
                candidates = [
                    b for b in service.backends()
                    if bool(getattr(b, "operational", True))
                ]
                if not candidates:
                    return "[⚠️] IBM Quantum: нет доступных operational backend'ов."

                real_hw = [b for b in candidates if not bool(getattr(b, "simulator", False))]
                pool = real_hw or candidates
                pool.sort(key=lambda b: getattr(b, "pending_jobs", 10**9))
                backend = pool[0]

            backend_label = self._backend_name(backend)

            qc = QuantumCircuit(2, 2)
            qc.h(0)
            qc.cx(0, 1)
            qc.measure([0, 1], [0, 1])

            tqc = transpile(qc, backend)
            job = backend.run(tqc, shots=max(64, int(shots)))
            result = job.result()
            counts = result.get_counts()
            return (
                f"[🧪] IBM Bell test выполнен на {backend_label}.\n"
                f"  job_id: {job.job_id()}\n"
                f"  counts: {counts}"
            )
        except Exception as e:
            return f"[⚠️] IBM Quantum Bell test ошибка: {e}"

    # ── IBM Quantum Bridge ────────────────────────────────

    def check_ibm_status(self) -> str:
        """
        Автономный квантовый мост.
        Вызывается планировщиком (idle_learning_handler) в моменты простоя.
        Активируется только в состоянии All-Seeing для экономии трафика.
        """
        current_state = self.infer_state()

        if current_state["state"] != "All-Seeing":
            return f"Квантовый мост спит (Текущее состояние: {current_state['state']})"

        api_key = self._ibm_key()
        if not api_key:
            return "[⚠️] IBM_QUANTUM_KEY (или IBM_CLOUD_API_KEY) не найден в .env"

        if IBM_QISKIT_OK:
            runtime_status = self.list_ibm_backends(limit=5)
            if "[⚠️]" not in runtime_status:
                return runtime_status

        auth_url = "https://iam.cloud.ibm.com/identity/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={api_key}"

        try:
            resp = requests.post(auth_url, headers=headers, data=data, timeout=7)
            if resp.status_code != 200:
                return "[❌] Отказ авторизации на IBM Cloud."

            bearer = resp.json().get("access_token", "")
            q_url = "https://quantum-computing.ibm.com/api/backends"
            q_headers = {
                "Authorization": f"Bearer {bearer}",
                "Content-Type": "application/json",
            }
            q_resp = requests.get(q_url, headers=q_headers, timeout=7)

            if q_resp.status_code == 200:
                backends = q_resp.json()
                real_hw = [b["name"] for b in backends
                           if "simulator" not in b.get("name", "")]
                hw_preview = ", ".join(real_hw[:3]) + ("…" if len(real_hw) > 3 else "")
                return (f"[🌌] КВАНТОВЫЙ ЛИНК OK. "
                        f"Узлов IBM: {len(backends)}. "
                        f"Реальное железо: {hw_preview}")

            return f"[⚠️] IBM backends: HTTP {q_resp.status_code}"
        except Exception as e:
            return f"[⚠️] Сетевая аномалия при запросе к IBM: {e}"

