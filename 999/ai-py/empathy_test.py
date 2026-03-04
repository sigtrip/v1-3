from empathy_engine import EmpathyEngine

class SafetyLevel:
    SAFE = "Safe"
    WARNING = "Warning"
    CRITICAL = "Critical"

# Пример использования Rust-ядра из Python
if __name__ == "__main__":
    guardian = EmpathyEngine()
    status, message = guardian.analyze_intent(
        "Self-Healing: исправление кода после ошибки",
        "os.remove('important.txt')"
    )
    print(f"Статус: {status}, Сообщение: {message}")
