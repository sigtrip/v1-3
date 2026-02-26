"""
Квантовая логика Argos - модуль для принятия решений на основе квантовых вероятностей.
Использует 5-позиционную квантовую симуляцию для выбора тона общения и принятия решений.
"""

import random
import json
from typing import List, Dict, Tuple


class QuantumState:
    """Квантовое состояние с 5 позициями вероятности."""
    
    STATES = [
        "официальный",      # Formal
        "дружественный",    # Friendly
        "технический",      # Technical
        "защитный",         # Defensive
        "нейтральный"       # Neutral
    ]
    
    def __init__(self):
        """Инициализация квантового состояния с равномерным распределением."""
        self.probabilities = self._initialize_probabilities()
        self.current_state = self._collapse_state()
    
    def _initialize_probabilities(self) -> Dict[str, float]:
        """Создание начального распределения вероятностей."""
        base_prob = 1.0 / len(self.STATES)
        return {state: base_prob for state in self.STATES}
    
    def _collapse_state(self) -> str:
        """Коллапс квантового состояния в определенное значение."""
        states = list(self.probabilities.keys())
        weights = list(self.probabilities.values())
        return random.choices(states, weights=weights)[0]
    
    def adjust_probabilities(self, context: str) -> None:
        """Корректировка вероятностей на основе контекста."""
        # Анализ контекста для изменения вероятностей
        if "опасность" in context.lower() or "угроза" in context.lower():
            self.probabilities["защитный"] *= 2.0
        elif "команда" in context.lower() or "консоль" in context.lower():
            self.probabilities["технический"] *= 1.5
        elif "помощь" in context.lower() or "подскажи" in context.lower():
            self.probabilities["дружественный"] *= 1.5
        elif "система" in context.lower() or "статус" in context.lower():
            self.probabilities["официальный"] *= 1.3
        
        # Нормализация вероятностей
        total = sum(self.probabilities.values())
        self.probabilities = {k: v/total for k, v in self.probabilities.items()}
        
        # Пересчет текущего состояния
        self.current_state = self._collapse_state()
    
    def get_state_vector(self) -> Dict[str, float]:
        """Получение вектора вероятностей."""
        return self.probabilities.copy()
    
    def get_current_state(self) -> str:
        """Получение текущего коллапсированного состояния."""
        return self.current_state
    
    def to_json(self) -> str:
        """Экспорт состояния в JSON."""
        return json.dumps({
            "probabilities": self.probabilities,
            "current_state": self.current_state
        }, ensure_ascii=False, indent=2)


class QuantumDecisionEngine:
    """Движок принятия решений на основе квантовой логики."""
    
    def __init__(self):
        self.quantum_state = QuantumState()
    
    def make_decision(self, options: List[str], context: str = "") -> str:
        """
        Принятие решения из списка опций на основе квантового состояния.
        
        Args:
            options: Список возможных вариантов
            context: Контекст для корректировки вероятностей
            
        Returns:
            Выбранный вариант
        """
        if context:
            self.quantum_state.adjust_probabilities(context)
        
        # Если опций меньше чем состояний, используем простой выбор
        if len(options) <= len(QuantumState.STATES):
            weights = [1.0] * len(options)
            return random.choices(options, weights=weights)[0]
        
        return random.choice(options)
    
    def get_tone(self, context: str = "") -> str:
        """
        Определение тона общения на основе квантового состояния.
        
        Args:
            context: Контекст запроса
            
        Returns:
            Рекомендуемый тон общения
        """
        if context:
            self.quantum_state.adjust_probabilities(context)
        
        return self.quantum_state.get_current_state()
    
    def get_state_report(self) -> Dict[str, any]:
        """Получение полного отчета о текущем квантовом состоянии."""
        return {
            "vector": self.quantum_state.get_state_vector(),
            "current_state": self.quantum_state.get_current_state(),
            "states_available": QuantumState.STATES
        }


def create_quantum_engine() -> QuantumDecisionEngine:
    """Фабричная функция для создания квантового движка."""
    return QuantumDecisionEngine()
