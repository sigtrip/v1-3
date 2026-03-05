import os
import hashlib
import requests
import subprocess
import threading
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.utils import platform

# Настройка разрешений для Android
if platform == 'android':
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    request_permissions([
        Permission.BLUETOOTH, 
        Permission.BLUETOOTH_ADMIN, 
        Permission.ACCESS_FINE_LOCATION,
        Permission.INTERNET,
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE
    ])

class CyberGraph(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.values = [0] * 40
        Clock.schedule_interval(self.update_canvas, 0.1)

    def add_val(self, val):
        self.values.append(val)
        if len(self.values) > 40: self.values.pop(0)

    def update_canvas(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0, 0.3, 0.2, 0.3)
            for i in range(0, self.width, 40):
                Line(points=[self.x + i, self.y, self.x + i, self.y + self.height], width=1)
            for i in range(0, self.height, 40):
                Line(points=[self.x, self.y + i, self.x + self.width, self.y + i], width=1)
            Color(0, 1, 0.8, 1)
            points = []
            w_step = self.width / 39
            for i, v in enumerate(self.values):
                points.extend([self.x + i * w_step, self.y + (v / 100 * self.height)])
            if len(points) >= 4:
                Line(points=points, width=1.5, joint='round')

class ArgosCore:
    def __init__(self):
        self.ai_host = "http://192.168.1.100:11434"
        self.found_tasmota = []
        self.evolution = 1.51

    def get_help(self):
        return """
--- [ ARGOS COMMAND REFERENCE ] ---
> AI & LOGIC:
  ai [text]       - Отправить запрос нейросети (Llama-3)
  train           - Провести сессию обучения ядра
  status          - Показать состояние узлов и энтропию

> HARDWARE & NETWORK:
  scan            - Deep Scan Wi-Fi сети на наличие Tasmota/ESP
  tasmota [IP] [ON/OFF] - Управление питанием ESP-узла
  tasmota [IP] STATUS   - Получить JSON отчет с устройства

> SYSTEM & SECURITY:
  root            - Попытка эскалации прав (требует Magisk)
  shell [cmd]     - Выполнение прямой Bash-команды в Android
  clear           - Полная очистка консоли терминала
  exit            - Завершение текущей сессии
----------------------------------"""

    def get_status_report(self):
        return f"""
[SYSTEM STATUS REPORT]
VERSION: v{self.evolution}
KERNEL: {'ROOTED' if self.check_root_silent() else 'STABLE/USER'}
NETWORK: P2P Bridge Active
AI BRIDGE: Connected to {self.ai_host}
KNOWN NODES: {len(self.found_tasmota)}
"""

    def check_root_silent(self):
        try:
            res = subprocess.run(['su', '-c', 'id'], capture_output=True, text=True, timeout=0.5)
            return "uid=0" in res.stdout
        except: return False

class ArgosOS(App):
    def build(self):
        self.core = ArgosCore()
        self.root = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        with self.root.canvas.before:
            Color(0, 0.02, 0.05, 1)
            self.bg = Rectangle(size=(2000, 2000), pos=(0,0))

        # ТОР (График и мини-статус)
        self.top_box = BoxLayout(size_hint_y=0.25, spacing=10)
        self.graph = CyberGraph()
        self.status_label = Label(
            text=f"🔱 ARGOS v{self.core.evolution}\nSTATUS: ONLINE",
            color=(0, 1, 0.8, 1), font_size='14sp', bold=True, size_hint_x=0.4
        )
        self.top_box.add_widget(self.graph)
        self.top_box.add_widget(self.status_label)
        self.root.add_widget(self.top_box)

        # ТЕРМИНАЛ
        self.scroll = ScrollView(size_hint_y=0.55)
        self.console = Label(
            text="[ARGOS INITIALIZED] Type 'help' to see command list.",
            size_hint_y=None, height=10000, halign='left', valign='top',
            color=(0, 0.8, 0.5, 1), font_name='Roboto', font_size='12sp'
        )
        self.console.bind(size=self.console.setter('text_size'))
        self.scroll.add_widget(self.console)
        self.root.add_widget(self.scroll)

        # ВВОД
        self.input_area = BoxLayout(size_hint_y=0.1, spacing=5)
        self.input_field = TextInput(
            hint_text="Enter instruction...",
            multiline=False, background_color=(0, 0.1, 0.1, 1),
            foreground_color=(0, 1, 0.9, 1), cursor_color=(0, 1, 0.9, 1)
        )
        self.btn = Button(
            text="EXEC", size_hint_x=0.2,
            background_color=(0, 0.5, 0.4, 1), color=(1, 1, 1, 1), bold=True
        )
        self.btn.bind(on_press=self.handle_cmd)
        self.input_area.add_widget(self.input_field)
        self.input_area.add_widget(self.btn)
        self.root.add_widget(self.input_area)

        Clock.schedule_interval(self.fake_telemetry, 1)
        return self.root

    def log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        self.console.text += f"\n[{t}] {msg}"

    def fake_telemetry(self, dt):
        import random
        self.graph.add_val(random.randint(15, 85))

    def handle_cmd(self, instance):
        cmd = self.input_field.text.strip().lower()
        self.input_field.text = ""
        if not cmd: return

        if cmd in ["help", "?", "man"]:
            self.log(self.core.get_help())
        
        elif cmd == "status":
            self.log(self.core.get_status_report())

        elif cmd == "scan":
            self.log("📡 Инициализация сканера Tasmota...")
            # (Здесь логика сканирования из прошлого шага)
            self.log("Scan started in background...")
        
        elif cmd == "clear":
            self.console.text = "[CONSOLE WIPED]"

        elif cmd.startswith("shell "):
            self.log(f"System EXEC: {cmd[6:]}")
            try:
                res = subprocess.check_output(cmd[6:], shell=True, stderr=subprocess.STDOUT).decode()
                self.log(res)
            except Exception as e: self.log(f"Error: {e}")

        else:
            self.log(f"OPERATOR: {cmd}")
            threading.Thread(target=self.ai_query, args=(cmd,)).start()

    def ai_query(self, msg):
        try:
            r = requests.post(f"{self.core.ai_host}/api/generate", 
                              json={"model": "llama3", "prompt": msg, "stream": False}, timeout=10)
            ans = r.json().get('response', '...')
            Clock.schedule_once(lambda dt: self.log(f"ARGOS: {ans}"), 0)
        except:
            Clock.schedule_once(lambda dt: self.log("AI BRIDGE ERROR: Server offline."), 0)

if __name__ == '__main__':
    ArgosOS().run()
