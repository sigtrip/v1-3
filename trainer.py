import os
import json
from datetime import datetime

class ArgosTrainer:
    def __init__(self, brain_file="argos_brain.json"):
        self.brain_file = brain_file
        self.experience_log = "experience_data.txt"
        self.knowledge_base = self.load_brain()

    def load_brain(self):
        if os.path.exists(self.brain_file):
            with open(self.brain_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"patterns": {}, "total_commands": 0, "evolution_level": 1.0}

    def save_brain(self):
        with open(self.brain_file, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_base, f, indent=4)

    def log_interaction(self, user_input, system_output):
        """Записывает опыт для последующего анализа"""
        with open(self.experience_log, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().isoformat()
            f.write(f"{timestamp} | IN: {user_input} | OUT: {system_output}\n")

    def train_on_history(self):
        """Простейший анализ паттернов: что пользователь делает чаще всего"""
        if not os.path.exists(self.experience_log):
            return "No experience data found to train."

        with open(self.experience_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Логика 'эволюции': каждые 10 команд повышают уровень системы
        self.knowledge_base["total_commands"] = len(lines)
        new_level = 1.0 + (len(lines) / 100)
        self.knowledge_base["evolution_level"] = round(new_level, 2)
        
        self.save_brain()
        return f"Evolution Complete. Level: {self.knowledge_base['evolution_level']}. Samples processed: {len(lines)}"

    def get_system_prompt(self):
        """Генерирует динамический промпт для ИИ на основе уровня эволюции"""
        level = self.knowledge_base["evolution_level"]
        return f"You are ARGOS OS. Your current Evolution Level is {level}. Be highly efficient and autonomous."
