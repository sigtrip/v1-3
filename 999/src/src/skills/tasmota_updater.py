"""
tasmota_updater.py — Автоматическое скачивание свежих прошивок Tasmota
"""
import os
import requests
import logging

log = logging.getLogger("argos.skills.tasmota_updater")

class TasmotaUpdater:
    def __init__(self):
        # Базовый URL официального OTA-сервера Tasmota
        self.base_url = "http://ota.tasmota.com/tasmota/release/"
        
        # Какие файлы качаем и как переименовываем для Smart Flasher Аргоса
        self.targets = {
            "tasmota.bin": "tasmota_relay.bin",
            "tasmota-sensors.bin": "tasmota_sensor.bin",
            "tasmota-ru.bin": "tasmota_ru_relay.bin" # На всякий случай русскую версию тоже
        }
        
        # Определяем папку для сохранения (поднимаемся из src/skills в корень и идем в assets)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.firmware_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "assets", "firmware"))

    def _ensure_dir(self):
        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)
            log.info(f"📁 Создана директория для прошивок: {self.firmware_dir}")

    def execute(self, text: str = "", core=None) -> str:
        """Метод, который вызывает Аргос при активации навыка."""
        self._ensure_dir()
        results = []
        
        for tasmota_file, argos_name in self.targets.items():
            download_url = self.base_url + tasmota_file
            save_path = os.path.join(self.firmware_dir, argos_name)
            
            try:
                log.info(f"🌐 Скачивание {tasmota_file}...")
                response = requests.get(download_url, stream=True, timeout=15)
                
                if response.status_code == 200:
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    results.append(f"✅ {argos_name} обновлен.")
                else:
                    results.append(f"❌ Ошибка 404: {tasmota_file} не найден на сервере.")
                    
            except Exception as e:
                log.error(f"Ошибка скачивания {tasmota_file}: {e}")
                results.append(f"❌ Ошибка сети при скачивании {tasmota_file}.")

        summary = "\n".join(results)
        return f"🔄 **Отчёт об обновлении прошивок Tasmota:**\n{summary}"

# Для динамической загрузки через SkillLoader
def setup():
    return TasmotaUpdater()
