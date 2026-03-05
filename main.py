import os
import sys

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

# Добавляем путь к src для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class ArgosInterface(App):
    def build(self):
        layout = BoxLayout(orientation="vertical", padding=30, spacing=20)

        # Заголовок
        self.status = Label(
            text="🔱 ARGOS v1.3 [OFFLINE MODE]\nSTATUS: AWAITING AUTHENTICATION",
            halign="center",
            font_size="20sp",
        )

        self.key_input = TextInput(
            hint_text="Enter Master Key (SHA-256 hash)...",
            multiline=False,
            size_hint=(1, 0.2),
            password=True,  # Скрыть ввод
        )

        btn = Button(text="ACTIVATE SYSTEM", size_hint=(1, 0.3), background_color=(0, 0.7, 1, 1))
        btn.bind(on_press=self.activate)

        layout.add_widget(self.status)
        layout.add_widget(self.key_input)
        layout.add_widget(btn)
        return layout

    def activate(self, instance):
        key = self.key_input.text.strip()

        # Базовая валидация ключа
        if not key:
            self.status.text = "❌ KEY REQUIRED"
            return

        if len(key) != 64:
            self.status.text = "❌ INVALID KEY LENGTH\nExpected: 64 chars (SHA-256)"
            return

        # Проверка формата (hex)
        try:
            int(key, 16)
        except ValueError:
            self.status.text = "❌ INVALID KEY FORMAT\nExpected: hexadecimal SHA-256"
            return

        # Попытка авторизации через backend
        try:
            from src.security.master_auth import get_auth

            auth = get_auth()

            if auth.verify(key):
                self.status.text = "✅ AUTHENTICATION SUCCESSFUL\n🔓 ARGOS SYSTEM ONLINE\nInitializing modules..."
                self.key_input.disabled = True
                instance.disabled = True

                # TODO: Запустить основной функционал Argos
                # from src.core import ArgosCore
                # self.argos_core = ArgosCore()
            else:
                self.status.text = "❌ AUTHENTICATION FAILED\nInvalid master key"
        except ImportError as e:
            # Fallback если backend недоступен
            self.status.text = f"⚠️ OFFLINE MODE\nBackend unavailable: {str(e)[:50]}"
        except Exception as e:
            self.status.text = f"❌ ERROR: {str(e)[:100]}"


if __name__ == "__main__":
    ArgosInterface().run()
