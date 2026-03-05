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

# Интеграция с Android
if platform == 'android':
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    request_permissions([Permission.BLUETOOTH, Permission.BLUETOOTH_ADMIN, Permission.ACCESS_FINE_LOCATION])

class GraphWidget(BoxLayout):
    """Виджет для отрисовки графиков телеметрии"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.points = []
        self.max_points = 50
        bind_f = lambda *args: self.redraw()
        self.bind(size=bind_f, pos=bind_f)

    def add_value(self, value):
        self.points.append(value)
        if len(self.points) > self.max_points:
            self.points.pop(0)
        self.redraw()

    def redraw(self, *args):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(0, 1, 0, 0.5) # Полупрозрачный зеленый
            if len(self.points) > 1:
                w, h = self.size
                step = w / self.max_points
                points_to_draw = []
                for i, v in enumerate(self.points):
                    x = self.x + (i * step)
                    y = self.y + (v / 100 * h)
                    points_to_draw.extend([x, y])
                Line(points=points_to_draw, width=1.5)

class ArgosCore:
    def __init__(self):
        self.ai_server = "http://192.168.1.100:11434" # Замени на свой IP

    def tasmota_cmd(self, ip, command):
        """Управление устройствами Tasmota через HTTP API"""
        # command может быть 'ON', 'OFF', 'STATUS', 'TOGGLE'
        try:
            url = f"http://{ip}/cm?cmnd=Power%20{command}"
            r = requests.get(url, timeout=3)
            return f"[TASMOTA] Result: {r.json()}"
        except Exception as e:
            return f"[TASMOTA ERROR] Link failed: {e}"

    def execute_shell(self, cmd):
        try:
            return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
        except Exception as e:
            return str(e)

class ArgosInterface(App):
    def build(self):
        self.core = ArgosCore()
        self.main_layout = BoxLayout(orientation='vertical', padding=5, spacing=5)
        
        # 1. Секция графиков (Телеметрия)
        self.graph = GraphWidget(size_hint=(1, 0.2))
        self.main_layout.add_widget(self.graph)
        Clock.schedule_interval(self.update_telemetry, 1)

        # 2. Заголовок
        self.header = Label(
            text="🔱 ARGOS v1.4.0 OVERLORD",
            size_hint=(1, 0.05), color=(0, 1, 0.6, 1), bold=True
        )
        self.main_layout.add_widget(self.header)

        # 3. Консоль
        self.scroll = ScrollView(size_hint=(1, 0.6))
        self.console = Label(
            text="[CORE INITIALIZED] Tasmota-ESP Protocol Ready.",
            size_hint_y=None, height=5000, halign='left', valign='top',
            color=(0, 0.8, 0.2, 1), font_size='12sp'
        )
        self.console.bind(size=self.console.setter('text_size'))
        self.scroll.add_widget(self.console)
        self.main_layout.add_widget(self.scroll)

        # 4. Ввод
        self.input_field = TextInput(
            hint_text="ai: [msg], tasmota: [ip] [cmd], shell: [cmd]",
            multiline=False, size_hint=(1, 0.08),
            background_color=(0, 0.05, 0, 1), foreground_color=(0, 1, 0, 1)
        )
        self.main_layout.add_widget(self.input_field)

        self.btn = Button(
            text="PROCESS", size_hint=(1, 0.07),
            background_color=(0, 0.3, 0.1, 1), on_press=self.handle_input
        )
        self.main_layout.add_widget(self.btn)
        
        return self.main_layout

    def log(self, msg):
        now = datetime.now().strftime("%H:%M:%S")
        self.console.text += f"\n[{now}] {msg}"

    def update_telemetry(self, dt):
        # Имитация получения данных (в APK можно заменить на реальный psutil, если есть root)
        val = (datetime.now().second % 60) + 20 
        self.graph.add_value(val)

    def handle_input(self, instance):
        text = self.input_field.text.strip()
        self.input_field.text = ""
        if not text: return

        # Логика команд
        if text.startswith("tasmota "):
            # Формат: tasmota 192.168.1.50 ON
            parts = text.split(" ")
            if len(parts) == 3:
                res = self.core.tasmota_cmd(parts[1], parts[2])
                self.log(res)
            else:
                self.log("Usage: tasmota [IP] [ON/OFF/STATUS]")

        elif text.startswith("shell "):
            self.log(f"Exec: {text[6:]}")
            self.log(self.core.execute_shell(text[6:]))

        elif text == "clear":
            self.console.text = ""

        else:
            # Отправка в ИИ
            self.log(f"Operator: {text}")
            threading.Thread(target=self.ai_brain, args=(text,)).start()

    def ai_brain(self, prompt):
        # Системный промпт для "автономности"
        sys_prompt = "You are ARGOS AI. If the user asks for a system action, reply with EXEC: [command]. "
        try:
            r = requests.post(f"{self.core.ai_server}/api/generate", 
                              json={"model": "llama3", "prompt": f"{sys_prompt} User: {prompt}", "stream": False},
                              timeout=10)
            answer = r.json().get('response', '')
            
            # Автономное выполнение, если ИИ выдал EXEC:
            if "EXEC:" in answer:
                cmd = answer.split("EXEC:")[1].strip()
                Clock.schedule_once(lambda dt: self.log(f"AI PROPOSAL: {cmd}"), 0)
                # Здесь можно добавить автоматическое выполнение, но лучше оставить подтверждение
            
            Clock.schedule_once(lambda dt: self.log(f"ARGOS: {answer}"), 0)
        except:
            Clock.schedule_once(lambda dt: self.log("ARGOS: AI Bridge Error."), 0)

if __name__ == '__main__':
    ArgosInterface().run()
