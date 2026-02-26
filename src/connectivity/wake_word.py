"""
wake_word.py — Wake Word детектор
  Постоянно слушает микрофон. При обнаружении "аргос" / "argos"
  активирует полный цикл прослушивания → ответа → TTS.
"""
import threading
import time
from src.argos_logger import get_logger

log = get_logger("argos.wake")

WAKE_WORDS = ["аргос", "argos", "аргас", "аргоc"]


class WakeWordListener:
    def __init__(self, core, admin, flasher):
        self.core    = core
        self.admin   = admin
        self.flasher = flasher
        self._running = False
        self._active  = False  # True когда уже обрабатываем команду

    def start(self) -> str:
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()
        log.info("Wake Word активен. Жду: %s", WAKE_WORDS)
        return f"👂 Wake Word активен. Скажи «Аргос» для активации."

    def stop(self):
        self._running = False
        return "Wake Word отключён."

    def _loop(self):
        try:
            import speech_recognition as sr
        except ImportError:
            log.error("SpeechRecognition не установлен: pip install SpeechRecognition")
            return

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True

        while self._running:
            if self._active:
                time.sleep(0.5)
                continue
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    log.debug("Слушаю wake word...")
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)

                text = recognizer.recognize_google(audio, language="ru-RU").lower()
                log.debug("Услышал: %s", text)

                if any(w in text for w in WAKE_WORDS):
                    log.info("Wake word обнаружен!")
                    self._handle_activation(recognizer)

            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception as e:
                log.error("Wake word ошибка: %s", e)
                time.sleep(2)

    def _handle_activation(self, recognizer):
        self._active = True
        self.core.say("Слушаю.")
        log.info("Активирован, жду команду...")

        try:
            import speech_recognition as sr
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = recognizer.listen(source, timeout=7, phrase_time_limit=15)

            command = recognizer.recognize_google(audio, language="ru-RU")
            log.info("Команда: %s", command)

            # Убираем wake word из начала
            cmd = command.lower()
            for w in WAKE_WORDS:
                if cmd.startswith(w):
                    cmd = cmd[len(w):].strip(" ,.")

            if cmd:
                result = self.core.process_logic(cmd, self.admin, self.flasher)
                # say() уже вызывается внутри process_logic
                log.info("Ответ: %s", result.get("answer","")[:80])

        except Exception as e:
            log.error("Ошибка команды: %s", e)
            self.core.say("Не понял команду.")
        finally:
            self._active = False
