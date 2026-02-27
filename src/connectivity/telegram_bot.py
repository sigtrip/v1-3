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
            "/crypto — BTC/ETH курсы\n"
            "/history — история диалога\n"
            "/geo — геолокация\n"
            "/memory — долгосрочная память\n"
            "/alerts — статус алертов\n"
            "/network — P2P сеть\n"
            "/sync — синхронизация навыков\n"
            "/replicate — создать копию\n"
            "/smart — умные системы\n"
            "/iot — IoT устройства\n"
            "`iot протоколы` — список поддерживаемых протоколов\n"
            "`статус устройства [id]` — мониторинг устройства\n"
            "`создай прошивку [id] [шаблон] [порт]` — подготовка/прошивка\n"
            "/skills — список навыков\n"
            "/voice_on /voice_off — озвучка\n"
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

    async def cmd_crypto(self, update, ctx):
        if not self._auth(update): return
        try:
            from src.skills.crypto_monitor import CryptoSentinel
            report = CryptoSentinel().report()
            await update.message.reply_text(report)
        except Exception as e:
            await update.message.reply_text(f"❌ Крипто: {e}")

    async def cmd_history(self, update, ctx):
        if not self._auth(update): return
        if self.core.db:
            hist = self.core.db.format_history(10)
            await update.message.reply_text(hist[:4000])
        else:
            await update.message.reply_text("БД не подключена.")

    async def cmd_geo(self, update, ctx):
        if not self._auth(update): return
        try:
            from src.connectivity.spatial import SpatialAwareness
            report = SpatialAwareness(db=self.core.db).get_full_report()
            await update.message.reply_text(report)
        except Exception as e:
            await update.message.reply_text(f"❌ Геолокация: {e}")

    async def cmd_memory(self, update, ctx):
        if not self._auth(update): return
        if self.core.memory:
            await update.message.reply_text(self.core.memory.format_memory()[:4000])
        else:
            await update.message.reply_text("Память не активирована.")

    async def cmd_alerts(self, update, ctx):
        if not self._auth(update): return
        if self.core.alerts:
            await update.message.reply_text(self.core.alerts.status())
        else:
            await update.message.reply_text("Система алертов не активирована.")

    async def cmd_replicate(self, update, ctx):
        if not self._auth(update): return
        await update.message.reply_text("📦 Создаю реплику системы...")
        try:
            result = self.core.replicator.create_replica()
            await update.message.reply_text(result)
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

    async def cmd_smart(self, update, ctx):
        """Статус умных систем."""
        if not self._auth(update): return
        if self.core.smart_sys:
            report = self.core.smart_sys.full_status()
            await update.message.reply_text(report[:4000])
        else:
            await update.message.reply_text("Умные системы не подключены.")

    async def cmd_iot(self, update, ctx):
        """Статус IoT устройств."""
        if not self._auth(update): return
        if self.core.iot_bridge:
            await update.message.reply_text(self.core.iot_bridge.status()[:4000])
        else:
            await update.message.reply_text("IoT Bridge не подключен.")

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
            "*IoT / Mesh / Прошивка:*\n"
            "• `iot статус` — сводка всех устройств\n"
            "• `статус устройства [id]` — детальный мониторинг устройства\n"
            "• `iot протоколы` — BACnet, Modbus, KNX, LonWorks, M-Bus, OPC UA, MQTT\n"
            "• `подключи zigbee [host] [port]` / `подключи lora [port] [baud]`\n"
            "• `запусти mesh` / `статус mesh`\n"
            "• `создай прошивку [id] [шаблон] [порт]` — создать/обновить прошивку\n"
            "• `шаблоны шлюзов` — доступные профили gateway\n\n"
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

        result = await self.core.process_logic_async(user_text, self.admin, self.flasher)
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
        self.app.add_handler(CommandHandler("crypto",    self.cmd_crypto))
        self.app.add_handler(CommandHandler("history",   self.cmd_history))
        self.app.add_handler(CommandHandler("geo",       self.cmd_geo))
        self.app.add_handler(CommandHandler("memory",    self.cmd_memory))
        self.app.add_handler(CommandHandler("alerts",    self.cmd_alerts))
        self.app.add_handler(CommandHandler("replicate", self.cmd_replicate))
        self.app.add_handler(CommandHandler("smart",     self.cmd_smart))
        self.app.add_handler(CommandHandler("iot",       self.cmd_iot))

        # Текстовые сообщения
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        print(f"[TG-BRIDGE]: Мост активен. USER_ID={self.user_id}")
        self.app.run_polling(close_loop=False)
