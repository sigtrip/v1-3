"""
Telegram Bot Adapter (универсальный, для Argos)
"""
from .base import BotAdapter
import os
try:
    from telegram import Update, Bot
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
    TELEGRAM_OK = True
except ImportError:
    TELEGRAM_OK = False

class TelegramAdapter(BotAdapter):
    def __init__(self, core, token=None):
        super().__init__(core)
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.updater = None

    def start(self):
        if not TELEGRAM_OK or not self.token:
            print("TelegramAdapter: библиотека или токен не найдены.")
            return
        self.updater = Updater(self.token, use_context=True)
        dp = self.updater.dispatcher
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self._on_message))
        self.updater.start_polling()
        print("TelegramAdapter: бот запущен.")

    def send_message(self, text, user=None):
        if self.updater and user:
            self.updater.bot.send_message(chat_id=user, text=text)

    def _on_message(self, update: Update, context: CallbackContext):
        user = update.effective_chat.id
        text = update.message.text
        result = self.handle_message(text, user)
        self.send_message(result.get("answer", "Нет ответа"), user)
