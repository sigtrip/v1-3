"""
Базовый адаптер для каналов (Telegram, Web, Discord, ...)
"""
class BotAdapter:
    def __init__(self, core):
        self.core = core

    def start(self):
        raise NotImplementedError()

    def send_message(self, text, user=None):
        raise NotImplementedError()

    def handle_message(self, text, user=None):
        # Обработка входящего сообщения, вызов ядра
        return self.core.process_logic(text, None, None)

"""
Базовый BotAdapter для поддержки мультиплатформенных ботов (inspired by awesome-bots).
"""
from abc import ABC, abstractmethod

class BotAdapter(ABC):
    def __init__(self, config=None):
        self.config = config or {}

    @abstractmethod
    def start(self):
        """Запуск бота/адаптера."""
        pass

    @abstractmethod
    def send_message(self, chat_id, text):
        """Отправить сообщение пользователю/чату."""
        pass

    @abstractmethod
    def handle_update(self, update):
        """Обработка входящего события/сообщения."""
        pass

    def set_middleware(self, middleware):
        """Установить middleware-цепочку (опционально)."""
        self.middleware = middleware

    def process_middlewares(self, update):
        """Пропустить update через middleware-цепочку (если есть)."""
        if hasattr(self, 'middleware') and self.middleware:
            for mw in self.middleware:
                update = mw(update)
        return update
