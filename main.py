import os
import hashlib
import requests
import subprocess
import threading
import importlib.util
import sys
from datetime import datetime

# Пытаемся импортировать Kivy. Если не выйдет - перейдем в текстовый режим.
GUI_MODE = True
try:
    os.environ['KIVY_NO_ARGS'] = '1'
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.textinput import TextInput
    from kivy.uix.button import Button
    from kivy.uix.scrollview import ScrollView
    from kivy.clock import Clock
    from kivy.graphics import Color, Rectangle, Line
    from kivy.utils import platform
except ImportError:
    GUI_MODE = False

# --- ЦВЕТА ДЛЯ КОНСОЛИ ---
G = '\033[92m' # Зеленый
B = '\033[94m' # Синий
R = '\033[91m' # Красный
W = '\033[0m'  # Белый

# --- ЯДРО ARGOS (Общее для GUI и CLI) ---
class ArgosCore:
    def __init__(self):
        self.ai_host = "http://localhost:11434"
        self.evolution = 1.62
        self.plugins = {}
        self.load_modules()

    def load_modules(self):
        if not os.path.exists('modules'): os.makedirs('modules')
        for file in os.listdir('modules'):
            if file.endswith('.py'):
                try:
                    mod_name = file[:-3]
                    spec = importlib.util.spec_from_file_location(mod_name, f"modules/{file}")
                    m = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(m)
                    self.plugins[mod_name] = m
                except: pass

    def execute_shell(self, cmd):
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            return output.decode('utf-8')
        except Exception as e:
            return f"Error: {str(e)}"

    def tasmota_power(self, ip, state):
        try:
            r = requests.get(f"http://{ip}/cm?cmnd=Power%20{state}", timeout=2)
            return f"[TASMOTA] Node {ip} -> {state}"
        except: return "[ERROR] Node offline"

    def get_help(self):
        p_list = ", ".join(self.plugins.keys())
        return f"Commands: help, status, shell [cmd], tasmota [ip] [on/off], clear, {p_list}"

# --- РЕЖИМ ТЕРМИНАЛА (CLI) ---
def run_terminal_mode(core):
    print(f"{G}")
    print(" 🔱 ARGOS UNIVERSAL OS v1.6.2")
    print(" [MODE: INTERACTIVE TERMINAL]")
    print(f" {W}Type 'help' for commands or 'exit' to quit.\n")
    
    while True:
        try:
            cmd = input(f"{G}Argos@System:~$ {W}").strip()
            if not cmd: continue
            if cmd.lower() in ['exit', 'quit']: break
            
            if cmd.lower() == 'help':
                print(f"{B}{core.get_help()}{W}")
            elif cmd.lower().startswith('shell '):
                print(core.execute_shell(cmd[6:]))
            elif cmd.lower() in core.plugins:
                print(core.plugins[cmd.lower()].execute(core, ""))
            elif cmd.lower().startswith('tasmota '):
                p = cmd.split(" ")
                if len(p) == 3: print(core.tasmota_power(p[1], p[2]))
            else:
                # ИИ через консоль
                print(f"{G}Thinking...{W}")
                try:
                    r = requests.post(f"{core.ai_host}/api/generate", 
                                      json={"model": "llama3", "prompt": cmd, "stream": False}, timeout=10)
                    print(f"{B}ARGOS AI: {r.json().get('response')}{W}")
                except:
                    print(f"{R}AI Offline.{W}")
        except KeyboardInterrupt:
            break

# --- РЕЖИМ ГРАФИКИ (KIVY) ---
if GUI_MODE:
    class CyberGraph(BoxLayout):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.values = [0] * 40
            Clock.schedule_interval(self.update, 0.1)
        def add_val(self, val):
            self.values.append(val); self.values.pop(0)
        def update(self, *args):
            self.canvas.after.clear()
            with self.canvas.after:
                Color(0, 1, 0.6, 1)
                points = []
                w_step = self.width / 39
                for i, v in enumerate(self.values):
                    points.extend([self.x + i * w_step, self.y + (v / 100 * self.height)])
                if len(points) >= 4: Line(points=points, width=1.5)

    class ArgosGUI(App):
        def build(self):
            self.core = ArgosCore()
            self.root = BoxLayout(orientation='vertical', padding=10, spacing=5)
            with self.root.canvas.before:
                Color(0, 0.03, 0.05, 1); Rectangle(size=(4000, 4000))
            self.graph = CyberGraph(size_hint_y=0.15)
            self.root.add_widget(self.graph)
            self.scroll = ScrollView(size_hint_y=0.75)
            self.console = Label(text="[GUI READY] Terminal Link Active.", size_hint_y=None, height=10000, halign='left', valign='top', color=(0, 1, 0.4, 1))
            self.console.bind(size=self.console.setter('text_size'))
            self.scroll.add_widget(self.console)
            self.root.add_widget(self.scroll)
            self.in_box = BoxLayout(size_hint_y=0.1, spacing=5)
            self.input_f = TextInput(multiline=False, background_color=(0, 0.08, 0.1, 1), foreground_color=(0, 1, 0.8, 1))
            self.btn = Button(text="EXE", size_hint_x=0.2); self.btn.bind(on_press=self.process)
            self.in_box.add_widget(self.input_f); self.in_box.add_widget(self.btn)
            self.root.add_widget(self.in_box)
            return self.root

        def log(self, msg):
            self.console.text += f"\n[{datetime.now().strftime('%H:%M')}] {msg}"

        def process(self, instance):
            cmd = self.input_f.text.strip(); self.input_f.text = ""
            if cmd.lower().startswith("shell "):
                self.log(self.core.execute_shell(cmd[6:]))
            else:
                self.log(f"Operator: {cmd}")
                # Тут логика ИИ...

# --- ТОЧКА ВХОДА ---
if __name__ == '__main__':
    core = ArgosCore()
    # Если запущен в Colab или нет X-сервера — включаем Терминал
    if not GUI_MODE or 'COLAB_GPU' in os.environ:
        run_terminal_mode(core)
    else:
        ArgosGUI().run()
