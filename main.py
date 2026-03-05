import os
import hashlib
import requests
import subprocess
import threading
import importlib.util
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line
from kivy.utils import platform

# --- ЯДРО СИСТЕМЫ ---
class ArgosCore:
    def __init__(self):
        self.ai_host = "http://localhost:11434"
        self.evolution_level = 1.60
        self.plugins = {}
        self.load_modules()

    def load_modules(self):
        """Динамическая загрузка навыков из папки modules"""
        if not os.path.exists('modules'):
            os.makedirs('modules')
        for file in os.listdir('modules'):
            if file.endswith('.py'):
                mod_name = file[:-3]
                spec = importlib.util.spec_from_file_location(mod_name, f"modules/{file}")
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                self.plugins[mod_name] = m

    def tasmota_power(self, ip, state):
        try:
            r = requests.get(f"http://{ip}/cm?cmnd=Power%20{state}", timeout=2)
            return f"[TASMOTA] {ip} -> {state}: {r.status_code}"
        except: return "[ERROR] Узел Tasmota недоступен"

# --- ИНТЕРФЕЙС ---
class CyberGraph(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.values = [0] * 40
        Clock.schedule_interval(self.update_canvas, 0.1)

    def add_val(self, val):
        self.values.append(val); self.values.pop(0)

    def update_canvas(self, *args):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(0, 1, 0.7, 1)
            points = []
            w_step = self.width / 39
            for i, v in enumerate(self.values):
                points.extend([self.x + i * w_step, self.y + (v / 100 * self.height)])
            if len(points) >= 4:
                Line(points=points, width=1.2)

class ArgosOS(App):
    def build(self):
        self.core = ArgosCore()
        self.root = BoxLayout(orientation='vertical', padding=10, spacing=5)
        with self.root.canvas.before:
            Color(0, 0.05, 0.08, 1); Rectangle(size=(3000, 3000))

        # График
        self.graph = CyberGraph(size_hint_y=0.2)
        self.root.add_widget(self.graph)

        # Консоль
        self.scroll = ScrollView(size_hint_y=0.7)
        self.console = Label(text="[SYSTEM ONLINE] v1.6.0 Ready.", size_hint_y=None, height=5000, 
                             halign='left', valign='top', color=(0, 0.9, 0.5, 1), font_size='13sp')
        self.console.bind(size=self.console.setter('text_size'))
        self.scroll.add_widget(self.console)
        self.root.add_widget(self.scroll)

        # Ввод
        self.in_box = BoxLayout(size_hint_y=0.1, spacing=5)
        self.input_f = TextInput(multiline=False, background_color=(0, 0.1, 0.1, 1), foreground_color=(0, 1, 0.8, 1))
        self.btn = Button(text="EXE", size_hint_x=0.2, background_color=(0, 0.4, 0.3, 1))
        self.btn.bind(on_press=self.process)
        self.in_box.add_widget(self.input_f); self.in_box.add_widget(self.btn)
        self.root.add_widget(self.in_box)
        
        Clock.schedule_interval(self.update_telemetry, 1)
        return self.root

    def log(self, msg):
        self.console.text += f"\n[{datetime.now().strftime('%H:%M')}] {msg}"

    def update_telemetry(self, dt):
        import random
        self.graph.add_val(random.randint(20, 80))

    def process(self, instance):
        cmd = self.input_f.text.strip(); self.input_f.text = ""
        if not cmd: return
        
        low_cmd = cmd.lower()
        if low_cmd == "help":
            self.log("COMMANDS: ai, tasmota [ip] [on/off], clear, " + ", ".join(self.core.plugins.keys()))
        elif low_cmd in self.core.plugins:
            self.log(f"Running Skill: {low_cmd}...")
            self.log(self.core.plugins[low_cmd].execute(self.core, ""))
        elif low_cmd.startswith("tasmota "):
            p = cmd.split(" ")
            if len(p) == 3: self.log(self.core.tasmota_power(p[1], p[2]))
        elif low_cmd == "clear": self.console.text = "[CLEARED]"
        else:
            self.log(f"User: {cmd}")
            threading.Thread(target=self.ai_call, args=(cmd,)).start()

    def ai_call(self, msg):
        try:
            r = requests.post(f"{self.core.ai_host}/api/generate", 
                              json={"model": "llama3", "prompt": msg, "stream": False}, timeout=15)
            ans = r.json().get('response', '...')
            Clock.schedule_once(lambda dt: self.log(f"ARGOS: {ans}"), 0)
        except: Clock.schedule_once(lambda dt: self.log("ARGOS: AI Offline."), 0)

if __name__ == '__main__': ArgosOS().run()
