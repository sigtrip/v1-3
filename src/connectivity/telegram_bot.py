import os
import asyncio
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes
)

class ArgosTelegram:
    def __init__(self, core, admin, flasher):
        self.core    = core
        self.admin   = admin
        self.flasher = flasher
        self.token   = os.getenv("TELEGRAM_BOT_TOKEN")
        self.user_id = os.getenv("USER_ID")
        self.app     = None

    # ── ПРОВЕРКА ДОСТУПА ──────────────────────────────────
    def _auth(self, update: Update) -> bool:
        if str(update.effective_user.id) != str(self.user_id):
            return False
        return True

    # ── КОМАНДЫ ───────────────────────────────────────────
    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        await update.message.reply_text(
            "👁️ *АРГОС ОНЛАЙН*\n\n"
            "Доступные команды:\n"
            "/status — здоровье системы\n"
            "/voice_on — включить озвучку\n"
            "/voice_off — выключить озвучку\n"
            "/skills — список навыков\n"
            "/help — справка\n\n"
            "Или просто напиши директиву текстом.",
            parse_mode="Markdown"
        )

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        stats  = self.admin.get_stats()
        health = self.core.sensors.get_full_report()
        state  = self.core.quantum.generate_state()
        msg = (
            f"📊 *СИСТЕМНЫЙ ДОКЛАД*\n\n"
            f"{stats}\n\n"
            f"{health}\n\n"
            f"⚛️ Квантовое состояние: `{state['name']}`\n"
            f"Вектор: `{state['vector']}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_voice_on(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        self.core.voice_on = True
        await update.message.reply_text("🔊 Голосовой модуль активирован.")

    async def cmd_voice_off(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        self.core.voice_on = False
        await update.message.reply_text("🔇 Голосовой модуль отключён.")

    async def cmd_skills(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        from src.evolution import ArgosEvolution
        report = ArgosEvolution().list_skills()
        await update.message.reply_text(report)

    async def cmd_network(self, update, ctx):
        if not self._auth(update): return
        if self.core.p2p:
            await update.message.reply_text(self.core.p2p.network_status())
        else:
            await update.message.reply_text("P2P не запущен.")

    async def cmd_sync(self, update, ctx):
        if not self._auth(update): return
        await update.message.reply_text("🔄 Синхронизирую навыки со всеми нодами...")
        if self.core.p2p:
            result = self.core.p2p.sync_skills_from_network()
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("P2P не запущен.")

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update): return
        help_text = (
            "👁️ *АРГОС — СПРАВОЧНИК*\n\n"
            "*Администрирование:*\n"
            "• `статус системы` — мониторинг ЦП/ОЗУ/диска\n"
            "• `покажи файлы [путь]` — содержимое папки\n"
            "• `прочитай файл [путь]` — чтение файла\n"
            "• `создай файл [имя] [текст]` — создать файл\n"
            "• `удали файл [путь]` — удалить файл\n"
            "• `консоль [команда]` — выполнить в терминале\n"
            "• `убей процесс [имя]` — завершить процесс\n\n"
            "*Навыки:*\n"
            "• `крипто` — цены BTC/ETH\n"
            "• `дайджест` — AI новости\n"
            "• `сканируй сеть` — устройства в сети\n"
            "• `сканируй порты` — открытые порты\n"
            "• `репликация` — создать архив системы\n\n"
            "*Голос:*\n"
            "• `/voice_on` / `/voice_off` — TTS\n"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    # ── ОСНОВНОЙ ОБРАБОТЧИК ───────────────────────────────
    async def handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._auth(update):
            await update.message.reply_text(
                "⛔ Доступ заблокирован. Попытка входа зафиксирована."
            )
            return

        user_text = update.message.text
        await update.message.reply_text("⚙️ Обрабатываю директиву...")

        result = self.core.process_logic(user_text, self.admin, self.flasher)
        answer = result['answer'][:4000]  # Telegram лимит
        state  = result['state']

        await update.message.reply_text(
            f"👁️ *ARGOS* `[{state}]`\n\n{answer}",
            parse_mode="Markdown"
        )

    # ── ЗАПУСК ────────────────────────────────────────────
    def run(self):
        if not self.token or self.token == "your_token_here":
            print("[TG-BRIDGE]: Токен не найден. Telegram-мост отключён.")
            return

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.app = Application.builder().token(self.token).build()

        # Команды
        self.app.add_handler(CommandHandler("start",     self.cmd_start))
        self.app.add_handler(CommandHandler("status",    self.cmd_status))
        self.app.add_handler(CommandHandler("voice_on",  self.cmd_voice_on))
        self.app.add_handler(CommandHandler("voice_off", self.cmd_voice_off))
        self.app.add_handler(CommandHandler("skills",    self.cmd_skills))
        self.app.add_handler(CommandHandler("help",      self.cmd_help))
        self.app.add_handler(CommandHandler("network",   self.cmd_network))
        self.app.add_handler(CommandHandler("sync",      self.cmd_sync))

        # Текстовые сообщения
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        print(f"[TG-BRIDGE]: Мост активен. USER_ID={self.user_id}")
        self.app.run_polling(close_loop=False)
