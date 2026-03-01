import random
import math
import time
import threading
import psutil
from datetime import datetime

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
