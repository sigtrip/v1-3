import os
import hashlib
import requests
import threading
from datetime import datetime
from trainer import ArgosTrainer # Импортируем нашего тренера

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock

class ArgosInterface(App):
    def build(self):
        self.trainer = ArgosTrainer() # Инициализация тренера
        self.ai_server = "http://127.0.0.1:11434" # IP для Ollama

        self.main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Header с отображением уровня эволюции
        level = self.trainer.knowledge_base["evolution_level"]
        self.header = Label(
            text=f"🔱 ARGOS OS v1.3.4 | EVOLUTION: {level}",
            size_hint=(1, 0.15), color=(0, 1, 0.5, 1), font_size='18sp', bold=True
        )
        self.main_layout.add_widget(self.header)

        self.scroll = ScrollView(size_hint=(1, 0.65))
        self.console = Label(
            text="[SYSTEM ONLINE] Trainer Module Loaded.",
            size_hint_y=None, height=5000, halign='left', valign='top',
            color=(0, 0.9, 0.1, 1), font_size='14sp'
        )
        self.console.bind(size=self.console.setter('text_size'))
        self.scroll.add_widget(self.console)
        self.main_layout.add_widget(self.scroll)

        self.input_field = TextInput(
            hint_text="Type 'train' to evolve or ask AI...",
            multiline=False, size_hint=(1, 0.1),
            background_color=(0, 0.1, 0, 1), foreground_color=(1, 1, 1, 1)
        )
        self.main_layout.add_widget(self.input_field)

        self.btn = Button(
            text="EXECUTE", size_hint=(1, 0.1),
            background_color=(0, 0.4, 0, 1), on_press=self.handle_input
        )
        self.main_layout.add_widget(self.btn)
        
        return self.main_layout

    def log(self, msg):
        self.console.text += f"\n[{datetime.now().strftime('%H:%M')}] {msg}"

    def handle_input(self, instance):
        cmd = self.input_field.text.strip()
        self.input_field.text = ""

        if cmd.lower() == "train":
            self.log("Starting neural evolution process...")
            result = self.trainer.train_on_history()
            self.log(result)
            self.header.text = f"🔱 ARGOS OS | EVOLUTION: {self.trainer.knowledge_base['evolution_level']}"
        
        elif cmd.lower() == "status":
            self.log(f"Commands processed: {self.trainer.knowledge_base['total_commands']}")
            self.log(f"Brain file: {self.trainer.brain_file}")
            
        else:
            self.log(f"User: {cmd}")
            threading.Thread(target=self.ai_request, args=(cmd,)).start()

    def ai_request(self, prompt):
        # Получаем кастомный промпт от тренера
        system_msg = self.trainer.get_system_prompt()
        try:
            r = requests.post(f"{self.ai_server}/api/generate", 
                              json={
                                  "model": "llama3", 
                                  "prompt": f"{system_msg}\nUser: {prompt}", 
                                  "stream": False
                              }, timeout=10)
            answer = r.json().get('response', '...')
            # Сохраняем опыт
            self.trainer.log_interaction(prompt, answer)
            Clock.schedule_once(lambda dt: self.log(f"ARGOS: {answer}"), 0)
        except:
            Clock.schedule_once(lambda dt: self.log("ARGOS: AI Server Offline."), 0)

if __name__ == '__main__':
    ArgosInterface().run()
