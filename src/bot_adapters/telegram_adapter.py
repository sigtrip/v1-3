"""
Telegram Bot Adapter (универсальный, для Argos)
"""

from src.bot_adapters.base import BotAdapter
import os

try:
    from telegram import Update, Bot
    from telegram.ext import Application, MessageHandler, filters, ContextTypes

    TELEGRAM_OK = True
except ImportError:

    class Update:
        pass

    class Bot:
        pass

    class Application:
        @staticmethod
        def builder():
            class B:
                def token(self, t):
                    return self

                def build(self):
                    return Application()

            return B()

        def add_handler(self, handler):
            pass

        async def run_polling(self):
            pass

        @property
        def bot(self):
            return Bot()

    class MessageHandler:
        pass

    class filters:
        TEXT = None
        COMMAND = None

    class ContextTypes:
        DEFAULT_TYPE = None

    TELEGRAM_OK = False

import asyncio


class TelegramAdapter(BotAdapter):
    def __init__(self, core, token=None):
        super().__init__(core)
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.app = None

    def start(self):
        if not TELEGRAM_OK or not self.token:
            print("TelegramAdapter: библиотека или токен не найдены.")
            return
        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._on_message))
        print("TelegramAdapter: бот запущен.")
        # Запуск асинхронно
        asyncio.get_event_loop().run_until_complete(self.app.run_polling())

    async def send_message(self, text, user=None):
        if self.app and user:
            await self.app.bot.send_message(chat_id=user, text=text)

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_chat.id
        text = update.message.text
        result = self.handle_message(text, user)
        await self.send_message(result.get("answer", "Нет ответа"), user)
