"""
Discord Bot Adapter (универсальный, для Argos)
"""
from .base import BotAdapter
import os
try:
    import discord
    DISCORD_OK = True
except ImportError:
    DISCORD_OK = False

class DiscordAdapter(BotAdapter):
    def __init__(self, core, token=None):
        super().__init__(core)
        self.token = token or os.getenv("DISCORD_BOT_TOKEN")
        self.client = None

    def start(self):
        if not DISCORD_OK or not self.token:
            print("DiscordAdapter: библиотека или токен не найдены.")
            return
        self.client = discord.Client()

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return
            result = self.handle_message(message.content, message.author.id)
            await message.channel.send(result.get("answer", "Нет ответа"))

        self.client.run(self.token)

    def send_message(self, text, user=None):
        # Для DiscordAdapter отправка реализуется через discord.py
        pass
