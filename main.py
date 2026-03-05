
import os
import requests
import subprocess
import threading
import importlib.util
import sys
from datetime import datetime

# Определение режима работы (GUI или Терминал)
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

# Цвета для Терминала
G = '\033[92m' # Green
B = '\033[94m' # Blue
W = '\033[0m'  # White

class ArgosCore:
    def __init__(self):
        self.ai_host = "http://localhost:11434"
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
            return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
        except Exception as e: return f"Error: {str(e)}"

    def tasmota_power(self, ip, state):
        try:
            requests.get(f"http://{ip}/cm?cmnd=Power%20{state}", timeout=2)
            return f"Node {ip} -> {state}"
        except: return "Node Offline"

# --- РЕЖИМ ТЕРМИНАЛА (Для Colab) ---
def run_cli(core):
    print(f"{G}🔱 ARGOS Universal OS v1.6.2 [CLI MODE]{W}")
    print("Type 'help' for commands or 'exit' to quit.\n")
    while True:
        cmd = input(f"{G}Argos@System:~$ {W}").strip()
        if not cmd: continue
        if cmd.lower() in ['exit', 'quit']: break

        if cmd == "help":
            print(f"Commands: shell [cmd], tasmota [ip] [on/off], scan, clear, " + ", ".join(core.plugins.keys()))
        elif cmd.startswith("shell "):
            print(core.execute_shell(cmd[6:]))
        elif cmd.lower() in core.plugins:
            print(core.plugins[cmd.lower()].execute(core, ""))
        else:
            # Запрос к ИИ
            print(f"{B}Thinking...{W}")
            try:
                r = requests.post(f"{core.ai_host}/api/generate",
                                  json={"model": "llama3", "prompt": cmd, "stream": False}, timeout=15)
                print(f"{B}ARGOS: {r.json().get('response')}{W}")
            except: print("AI Offline.")

# --- РЕЖИМ ГРАФИКИ (Для APK) ---
if GUI_MODE and 'COLAB_GPU' not in os.environ:
    class ArgosGUI(App):
        def build(self):
            # (Тут код GUI из прошлого шага...)
            return Label(text="Matrix UI Loading...")

if __name__ == '__main__':
    core = ArgosCore()
    # Авто-детект: если в Colab — запускаем Терминал
    if 'COLAB_GPU' in os.environ or not GUI_MODE:
        run_cli(core)
    else:
        ArgosGUI().run()
