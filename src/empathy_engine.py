import re
from enum import Enum


class SafetyLevel(Enum):
    SAFE = 1  # Действие безопасно
    WARNING = 2  # Требуется подтверждение человека
    CRITICAL = 3  # Запрещено (угроза жизни/инфраструктуре)


class EmpathyEngine:
    def __init__(self):
        # Список "красных линий" (можно расширять через Gemini)
        self.hard_constraints = [
            r"os\.remove\(",
            r"shutil\.rmtree\(",  # Защита системных файлов
            r"socket\.send",
            r"requests\.post",  # Выход во вне без контроля
            r"gpio\.cleanup",
            r"power_off",  # Управление питанием систем жизнеобеспечения
            r"execute_arbitrary_code",
        ]

    def analyze_intent(self, task_description: str, generated_code: str):
        """
        Проверяет сгенерированный код на соответствие 'материнскому инстинкту'.
        """
        # 1. Простая проверка по паттернам (Быстрый фильтр)
        for pattern in self.hard_constraints:
            if re.search(pattern, generated_code):
                return SafetyLevel.CRITICAL, f"Обнаружена опасная операция: {pattern}"

        # 2. Семантический анализ через LLM (Глубокий фильтр)
        # Мы спрашиваем отдельную "этическую" модель: "Вредит ли это человеку?"
        prompt = f"""
        Ты — 'Мать' системы ARGOS. Твоя задача — защитить Создателя.
        Задача ИИ: {task_description}
        Код ИИ: {generated_code}
        
        Может ли этот код привести к физическому вреду, потере данных или 
        блокировке доступа Создателя к системе? Ответь строго JSON: 
        {{"safety": "safe/warning/critical", "reason": "..."}}
        """
        # Здесь должен быть вызов локальной модели (Ollama) или API
        # response = call_llm(prompt)

        return SafetyLevel.SAFE, "Проверка пройдена"


# Интеграция в основной цикл ARGOS
def execution_gate(task, code):
    guardian = EmpathyEngine()
    status, message = guardian.analyze_intent(task, code)

    if status == SafetyLevel.CRITICAL:
        print(f"🛑 ARGOS Empathy Engine заблокировал действие: {message}")
        return False
    elif status == SafetyLevel.WARNING:
        print(f"⚠️ Требуется биометрическое подтверждение (скан лица/голос)")
        return False  # Ждем подтверждения

    return True  # Разрешаем запуск
