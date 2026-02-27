import random
import math
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
        
        # Факты о среде (Evidence)
        self.evidence = {
            "high_load": False,    # CPU > 70%
            "night_time": False,   # 22:00 - 06:00
            "user_active": True    # Активность пользователя (заглушка)
        }
        
    def _update_evidence(self):
        try:
            self.evidence["high_load"] = psutil.cpu_percent() > 70
        except:
            pass
            
        hour = datetime.now().hour
        self.evidence["night_time"] = (hour >= 22 or hour < 6)
        
        # TODO: Реальная проверка активности пользователя (клавиатура/мышь)
        
    def infer_state(self):
        """
        Рассчитывает наиболее вероятное состояние системы на основе Bayesian Inference.
        P(State | Evidence)
        """
        self._update_evidence()
        
        probs = {s: 0.1 for s in self.states} # Начнем с априорной вероятности (uniform + noise)
        
        # Таблицы условных вероятностей (hardcoded simplified CPT)
        # 1. Если высокая нагрузка -> P(Protective)++, P(Analytic)+
        if self.evidence["high_load"]:
            probs["Protective"] += 0.4
            probs["Analytic"]   += 0.2
            probs["Creative"]   -= 0.1
            
        # 2. Если ночь -> P(Creative)++, P(All-Seeing)+
        if self.evidence["night_time"]:
            probs["Creative"]   += 0.5
            probs["All-Seeing"] += 0.3
            probs["Analytic"]   -= 0.1
        else:
            probs["Analytic"]   += 0.3 # Днём мы аналитики
            
        # 3. Нормализация
        total = sum(probs.values())
        normalized_probs = {k: round(v/total, 3) for k, v in probs.items()}
        
        # Выбор наиболее вероятного (Max A Posteriori) или сэмплирование
        # Используем взвешенный выбор для "живости"
        states_list = list(normalized_probs.keys())
        weights     = list(normalized_probs.values())
        
        chosen_state = random.choices(states_list, weights=weights, k=1)[0]
        
        return {
            "state": chosen_state, 
            "vector": weights,
            "evidence": self.evidence,
            "probabilities": normalized_probs
        }

    def generate_state(self):
        # Совместимость со старым API
        # Возвращаем список вероятностей как вектор
        res = self.infer_state()
        vector_list = list(res["probabilities"].values())
        return {"name": res["state"], "vector": vector_list, "probabilities": res["probabilities"]}
