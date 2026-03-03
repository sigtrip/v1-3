"""
Web Bot Adapter (универсальный, для Argos)
"""
from .base import BotAdapter
from flask import Flask, request, jsonify
import threading

class WebAdapter(BotAdapter):
    def __init__(self, core, host="0.0.0.0", port=8080):
        super().__init__(core)
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route("/api/message", methods=["POST"])
        def message():
            data = request.get_json(force=True)
            text = data.get("text", "")
            user = data.get("user", None)
            result = self.handle_message(text, user)
            return jsonify(result)

    def start(self):
        threading.Thread(target=self.app.run, kwargs={"host": self.host, "port": self.port}, daemon=True).start()
        print(f"WebAdapter: сервер запущен на {self.host}:{self.port}")

    def send_message(self, text, user=None):
        # Для WebAdapter отправка реализуется через HTTP response
        pass
