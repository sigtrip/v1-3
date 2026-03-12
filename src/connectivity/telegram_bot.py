"""telegram_bot.py — Telegram-мост Аргоса"""
from __future__ import annotations
import os, threading
from src.argos_logger import get_logger
log = get_logger("argos.telegram")

class ArgosTelegramBot:
    def __init__(self, core=None):
        self.core = core
        self.token = os.getenv("TELEGRAM_BOT_TOKEN","")
        self.user_id = os.getenv("USER_ID","")
        self._running = False

    @property
    def configured(self): return bool(self.token and self.user_id)

    def start(self) -> str:
        if not self.configured:
            return "❌ Telegram не настроен. Укажи TELEGRAM_BOT_TOKEN и USER_ID в .env"
        try:
            from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
            self._app = ApplicationBuilder().token(self.token).build()
            self._app.add_handler(CommandHandler("start", self._cmd_start))
            self._app.add_handler(CommandHandler("status", self._cmd_status))
            self._app.add_handler(CommandHandler("help", self._cmd_help))
            self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))
            self._running = True
            t = threading.Thread(target=self._app.run_polling, daemon=True)
            t.start()
            log.info("Telegram bot: запущен")
            return "📱 Telegram-бот запущен."
        except ImportError:
            return "❌ Установи: pip install python-telegram-bot"
        except Exception as e:
            return f"❌ Telegram error: {e}"

    async def _cmd_start(self, update, ctx):
        await update.message.reply_text("🔱 Аргос онлайн. /help — список команд.")

    async def _cmd_status(self, update, ctx):
        if not self._auth(update): return
        r = self.core.process("статус системы") if self.core else {}
        await update.message.reply_text(r.get("answer","") if isinstance(r,dict) else str(r))

    async def _cmd_help(self, update, ctx):
        await update.message.reply_text(
            "🔱 АРГОС КОМАНДЫ:\n"
            "/status — состояние системы\n"
            "/help — эта справка\n"
            "Или просто напиши команду текстом."
        )

    async def _on_message(self, update, ctx):
        if not self._auth(update): return
        text = update.message.text or ""
        r = self.core.process(text) if self.core else {"answer":"Core недоступен"}
        answer = r.get("answer","") if isinstance(r,dict) else str(r)
        await update.message.reply_text(answer[:4000])

    def _auth(self, update) -> bool:
        if not self.user_id: return True
        return str(update.effective_user.id) == str(self.user_id)

    def send(self, text: str) -> bool:
        if not self.configured or not self._running: return False
        try:
            import asyncio, telegram
            bot = telegram.Bot(self.token)
            asyncio.run(bot.send_message(chat_id=self.user_id, text=text[:4000]))
            return True
        except Exception as e:
            log.warning("Telegram send: %s", e)
            return False

    def status(self) -> str:
        return (f"📱 Telegram: {'✅ запущен' if self._running else '⚠️ не запущен'}\n"
                f"  Настроен: {self.configured}\n"
                f"  User ID: {self.user_id or 'не указан'}")
