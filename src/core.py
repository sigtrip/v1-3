"""
core.py — ArgosCore FINAL v2.0
  Все подсистемы интегрированы:
  ИИ + Контекст + Голос + Wake Word + Память + Планировщик +
  Алерты + Агент + Vision + P2P + Загрузчик + 50+ команд
"""
import os, threading, requests

# ── Graceful imports ──────────────────────────────────────
try:
    import google.generativeai as genai; GEMINI_OK = True
except ImportError:
    genai = None; GEMINI_OK = False

try:
    import pyttsx3; PYTTSX3_OK = True
except ImportError:
    pyttsx3 = None; PYTTSX3_OK = False

try:
    import speech_recognition as sr; SR_OK = True
except ImportError:
    sr = None; SR_OK = False

from src.quantum.logic               import ArgosQuantum
from src.skills.web_scrapper         import ArgosScrapper
from src.factory.replicator          import Replicator
from src.connectivity.sensor_bridge  import ArgosSensorBridge
from src.connectivity.p2p_bridge     import ArgosBridge
from src.context_manager             import DialogContext
from src.agent                       import ArgosAgent
from src.argos_logger                import get_logger
from dotenv import load_dotenv
load_dotenv()

log = get_logger("argos.core")


class ArgosCore:
    def __init__(self):
        self.quantum    = ArgosQuantum()
        self.scrapper   = ArgosScrapper()
        self.replicator = Replicator()
        self.sensors    = ArgosSensorBridge()
        self.context    = DialogContext(max_turns=10)
        self.agent      = ArgosAgent(self)
        self.ollama_url = "http://localhost:11434/api/generate"
        self.voice_on   = True
        self.p2p        = None
        self.db         = None
        self.memory     = None
        self.scheduler  = None
        self.alerts     = None
        self.vision     = None
        self._boot      = None
        self._dashboard = None
        self._wake      = None
        self._tts_engine = None

        self._init_voice()
        self._setup_ai()
        self._init_memory()
        self._init_scheduler()
        self._init_alerts()
        self._init_vision()
        log.info("ArgosCore FINAL v2.0 инициализирован.")

    # ═══════════════════════════════════════════════════════
    # ИНИЦИАЛИЗАЦИЯ ПОДСИСТЕМ
    # ═══════════════════════════════════════════════════════
    def _init_memory(self):
        try:
            from src.memory import ArgosMemory
            self.memory = ArgosMemory()
            log.info("Память: OK")
        except Exception as e:
            log.warning("Память недоступна: %s", e)

    def _init_scheduler(self):
        try:
            from src.skills.scheduler import ArgosScheduler
            self.scheduler = ArgosScheduler(core=self)
            self.scheduler.start()
            log.info("Планировщик: OK")
        except Exception as e:
            log.warning("Планировщик: %s", e)

    def _init_alerts(self):
        try:
            from src.connectivity.alert_system import AlertSystem
            self.alerts = AlertSystem(on_alert=self._on_alert)
            self.alerts.start(interval_sec=30)
            log.info("Алерты: OK")
        except Exception as e:
            log.warning("Алерты: %s", e)

    def _init_vision(self):
        try:
            from src.vision import ArgosVision
            self.vision = ArgosVision()
            log.info("Vision: OK")
        except Exception as e:
            log.warning("Vision: %s", e)

    def _on_alert(self, msg: str):
        log.warning("ALERT: %s", msg)
        self.say(msg)

    # ═══════════════════════════════════════════════════════
    # P2P / DASHBOARD / WAKE WORD
    # ═══════════════════════════════════════════════════════
    def start_p2p(self) -> str:
        self.p2p = ArgosBridge(core=self)
        result = self.p2p.start()
        log.info("P2P: %s", result.split('\n')[0])
        return result

    def start_dashboard(self, admin, flasher, port: int = 8080) -> str:
        try:
            from src.interface.web_dashboard import WebDashboard
            self._dashboard = WebDashboard(self, admin, flasher, port)
            return self._dashboard.start()
        except Exception as e:
            return f"❌ Dashboard: {e}"

    def start_wake_word(self, admin, flasher) -> str:
        try:
            from src.connectivity.wake_word import WakeWordListener
            self._wake = WakeWordListener(self, admin, flasher)
            return self._wake.start()
        except Exception as e:
            return f"❌ Wake Word: {e}"

    # ═══════════════════════════════════════════════════════
    # ГОЛОС
    # ═══════════════════════════════════════════════════════
    def _init_voice(self):
        if not PYTTSX3_OK:
            log.warning("pyttsx3 не установлен: pip install pyttsx3")
            return
        try:
            self._tts_engine = pyttsx3.init()
            for v in self._tts_engine.getProperty('voices'):
                if "Russian" in v.name or "ru" in v.id:
                    self._tts_engine.setProperty('voice', v.id)
                    break
            self._tts_engine.setProperty('rate', 175)
            log.info("TTS: OK")
        except Exception as e:
            self._tts_engine = None
            log.warning("TTS недоступен: %s", e)

    def say(self, text: str):
        if not self.voice_on or not self._tts_engine:
            return
        def _speak():
            try:
                self._tts_engine.say(text[:300])
                self._tts_engine.runAndWait()
            except Exception: pass
        threading.Thread(target=_speak, daemon=True).start()

    def listen(self) -> str:
        if not SR_OK:
            log.warning("SpeechRecognition не установлен")
            return ""
        try:
            rec = sr.Recognizer()
            with sr.Microphone() as src:
                log.info("Слушаю...")
                rec.adjust_for_ambient_noise(src, duration=0.5)
                audio = rec.listen(src, timeout=7, phrase_time_limit=15)
                text  = rec.recognize_google(audio, language="ru-RU")
                log.info("Распознано: %s", text)
                return text.lower()
        except Exception as e:
            log.error("STT: %s", e)
            return ""

    # ═══════════════════════════════════════════════════════
    # ИИ
    # ═══════════════════════════════════════════════════════
    def _setup_ai(self):
        key = os.getenv("GEMINI_API_KEY", "")
        if GEMINI_OK and key and key != "your_key_here":
            genai.configure(api_key=key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            log.info("Gemini: OK")
        else:
            self.model = None
            log.info("Gemini недоступен — используется Ollama")

    def _ask_gemini(self, context: str, user_text: str) -> str | None:
        if not self.model:
            return None
        try:
            # Используем историю диалога для multi-turn
            history = self.context.get_gemini_messages()
            if history:
                chat = self.model.start_chat(history=history[:-1] if history else [])
                res  = chat.send_message(f"{context}\n\n{user_text}")
            else:
                res = self.model.generate_content([context, user_text])
            return res.text
        except Exception as e:
            log.error("Gemini: %s", e)
            return None

    def _ask_ollama(self, context: str, user_text: str) -> str | None:
        try:
            # Добавляем историю в промпт
            hist = self.context.get_prompt_context()
            full_prompt = f"{context}\n\n{hist}\n\nUser: {user_text}\nArgos:"
            res = requests.post(
                self.ollama_url,
                json={"model": "llama3", "prompt": full_prompt, "stream": False},
                timeout=15
            )
            return res.json().get('response')
        except Exception as e:
            log.error("Ollama: %s", e)
            return None

    # ═══════════════════════════════════════════════════════
    # ОСНОВНАЯ ЛОГИКА
    # ═══════════════════════════════════════════════════════
    def process_logic(self, user_text: str, admin, flasher) -> dict:
        q_data = self.quantum.generate_state()
        t = user_text.lower()

        # Проверяем напоминания
        if self.memory:
            for r in self.memory.check_reminders():
                self.say(r)

        # Агентный режим — цепочка задач
        agent_result = self.agent.execute_plan(user_text, admin, flasher)
        if agent_result:
            self.context.add("user", user_text)
            self.context.add("argos", agent_result)
            if self.db:
                self.db.log_chat("user", user_text)
                self.db.log_chat("argos", agent_result, "Agent")
            self.say("Агент выполнил задание.")
            return {"answer": agent_result, "state": "Agent"}

        # Одиночная команда
        intent = self.execute_intent(user_text, admin, flasher)
        if intent:
            self.context.add("user", user_text)
            self.context.add("argos", intent)
            if self.db:
                self.db.log_chat("user", user_text)
                self.db.log_chat("argos", intent, "System")
            self.say(intent)
            return {"answer": intent, "state": "System"}

        # Веб-поиск при необходимости
        if any(w in t for w in ["найди", "новости", "кто такой", "что такое"]):
            web = self.scrapper.quick_search(user_text)
            user_text = f"Данные из сети: {web}\nЗапрос: {user_text}"

        # Контекст + память для ИИ
        context = (
            f"Ты Аргос — всевидящий ИИ-ассистент. Квантовое состояние: {q_data['name']}. "
            f"Создатель: Всеволод. Год: 2026. Отвечай по-русски, кратко и по делу."
        )
        if self.memory:
            mc = self.memory.get_context()
            if mc:
                context += f"\n\n{mc}"

        answer = self._ask_gemini(context, user_text)
        engine = q_data['name']

        if not answer:
            answer = self._ask_ollama(context, user_text)
            engine = f"{q_data['name']} (Ollama)"

        if not answer:
            answer = "Связь с ядрами ИИ разорвана. Режим оффлайн."
            engine = "Offline"

        # Сохраняем в контекст и БД
        self.context.add("user", user_text)
        self.context.add("argos", answer)
        if self.db:
            self.db.log_chat("user", user_text)
            self.db.log_chat("argos", answer, engine)

        self.say(answer)
        return {"answer": answer, "state": engine}

    # ═══════════════════════════════════════════════════════
    # ДИСПЕТЧЕР КОМАНД — 50+ интентов
    # ═══════════════════════════════════════════════════════
    def execute_intent(self, text: str, admin, flasher) -> str | None:
        t = text.lower()

        # ── Мониторинг ────────────────────────────────────
        if any(k in t for k in ["статус системы", "чек-ап", "состояние здоровья"]):
            return f"{admin.get_stats()}\n{self.sensors.get_full_report()}"
        if "список процессов" in t:
            return admin.list_processes()
        if "выключи систему" in t:
            return admin.manage_power("shutdown")
        if any(k in t for k in ["убей процесс", "завершить процесс"]):
            return admin.kill_process(text.split()[-1])

        # ── Файлы ─────────────────────────────────────────
        if any(k in t for k in ["покажи файлы", "список файлов"]) or t.startswith("файлы "):
            path = text.replace("аргос","").replace("покажи файлы","").replace("список файлов","").replace("файлы","").strip()
            return admin.list_dir(path or ".")
        if "прочитай файл" in t or t.startswith("прочитай "):
            path = text.replace("аргос","").replace("прочитай файл","").replace("прочитай","").strip()
            return admin.read_file(path)
        if any(k in t for k in ["создай файл", "напиши файл"]):
            parts = text.replace("создай файл","").replace("напиши файл","").strip().split(maxsplit=1)
            return admin.create_file(parts[0] if parts else "note.txt", parts[1] if len(parts)>1 else "")
        if any(k in t for k in ["удали файл", "удали папку"]):
            return admin.delete_item(text.replace("аргос","").replace("удали файл","").replace("удали папку","").strip())

        # ── Терминал ──────────────────────────────────────
        if any(k in t for k in ["консоль", "терминал"]):
            cmd = text.split("консоль",1)[-1].strip() if "консоль" in t else text.split("терминал",1)[-1].strip()
            return admin.run_cmd(cmd)

        # ── Vision ────────────────────────────────────────
        if self.vision:
            if any(k in t for k in ["посмотри на экран", "что на экране", "скриншот"]):
                question = text.replace("аргос","").replace("посмотри на экран","").replace("что на экране","").replace("скриншот","").strip()
                return self.vision.look_at_screen(question or "Что происходит на экране?")
            if any(k in t for k in ["посмотри в камеру", "что видит камера", "включи камеру"]):
                question = text.replace("аргос","").replace("посмотри в камеру","").replace("что видит камера","").strip()
                return self.vision.look_through_camera(question or "Что ты видишь?")
            if "проанализируй изображение" in t or "анализ фото" in t:
                path = text.split()[-1]
                return self.vision.analyze_file(path)

        # ── Агент ─────────────────────────────────────────
        if "отчёт агента" in t or "последний план" in t:
            return self.agent.last_report()
        if "останови агента" in t:
            return self.agent.stop()

        # ── Контекст диалога ──────────────────────────────
        if any(k in t for k in ["сброс контекста", "забудь разговор", "новый диалог"]):
            return self.context.clear()
        if "контекст диалога" in t:
            return self.context.summary()

        # ── Репликация + IoT ──────────────────────────────
        if any(k in t for k in ["создай копию", "репликация"]):
            return self.replicator.create_replica()
        if "сканируй порты" in t:
            return f"Порты: {flasher.scan_ports()}"

        # ── Голос ─────────────────────────────────────────
        if any(k in t for k in ["голос вкл", "включи голос"]):
            self.voice_on = True; return "🔊 Голосовой модуль активирован."
        if any(k in t for k in ["голос выкл", "выключи голос"]):
            self.voice_on = False; return "🔇 Голосовой модуль отключён."
        if any(k in t for k in ["включи wake word", "wake word вкл"]):
            return self.start_wake_word(admin, flasher)

        # ── Навыки ────────────────────────────────────────
        if "дайджест" in t:
            from src.skills.content_gen import ContentGen
            return ContentGen().generate_digest()
        if "опубликуй" in t:
            from src.skills.content_gen import ContentGen
            return ContentGen().publish()
        if any(k in t for k in ["крипто", "биткоин", "bitcoin", "ethereum"]):
            from src.skills.crypto_monitor import CryptoSentinel
            return CryptoSentinel().report()
        if any(k in t for k in ["сканируй сеть", "сетевой призрак"]):
            from src.skills.net_scanner import NetGhost
            return NetGhost().scan()
        if any(k in t for k in ["список навыков", "навыки аргоса"]):
            from src.skills.evolution import ArgosEvolution
            return ArgosEvolution().list_skills()
        if any(k in t for k in ["напиши навык", "создай навык"]):
            from src.skills.evolution import ArgosEvolution
            desc = text.replace("напиши навык","").replace("создай навык","").strip()
            return ArgosEvolution(ai_core=self).generate_skill(desc)

        # ── Память ────────────────────────────────────────
        if self.memory:
            if "запомни" in t:
                return self.memory.parse_and_remember(text.replace("аргос","").replace("запомни","").strip())
            if any(k in t for k in ["что ты знаешь", "моя память", "покажи память"]):
                return self.memory.format_memory()
            if "забудь" in t and "разговор" not in t:
                return self.memory.forget(text.replace("аргос","").replace("забудь","").strip())
            if any(k in t for k in ["запиши заметку", "новая заметка"]):
                parts = text.replace("запиши заметку","").replace("новая заметка","").strip().split(":",1)
                return self.memory.add_note(parts[0].strip(), parts[1].strip() if len(parts)>1 else parts[0])
            if any(k in t for k in ["мои заметки", "список заметок"]):
                return self.memory.get_notes()
            if "прочитай заметку" in t:
                try: return self.memory.read_note(int(text.split()[-1]))
                except: return "Укажи номер: прочитай заметку 1"
            if "удали заметку" in t:
                try: return self.memory.delete_note(int(text.split()[-1]))
                except: return "Укажи номер: удали заметку 1"

        # ── Планировщик ───────────────────────────────────
        if self.scheduler:
            if any(k in t for k in ["расписание", "список задач"]):
                return self.scheduler.list_tasks()
            if any(k in t for k in ["каждые", "напомни", "ежедневно"]) or "через" in t:
                return self.scheduler.parse_and_add(text)
            if "удали задачу" in t:
                try: return self.scheduler.remove(int(text.split()[-1]))
                except: return "Укажи номер: удали задачу 1"

        # ── Алерты ────────────────────────────────────────
        if self.alerts:
            if any(k in t for k in ["статус алертов", "алерты"]):
                return self.alerts.status()
            if "установи порог" in t:
                try:
                    parts = text.split()
                    return self.alerts.set_threshold(parts[-2], float(parts[-1].replace("%","")))
                except: return "Формат: установи порог cpu 85"

        # ── Веб-панель ────────────────────────────────────
        if any(k in t for k in ["веб-панель", "веб панель", "dashboard", "открой панель"]):
            return self.start_dashboard(admin, flasher)

        # ── Геолокация ────────────────────────────────────
        if any(k in t for k in ["геолокация", "мой ip", "где я", "мой адрес"]):
            from src.connectivity.spatial import SpatialAwareness
            return SpatialAwareness(db=self.db).get_full_report()

        # ── Загрузчик ─────────────────────────────────────
        if any(k in t for k in ["загрузчик", "boot info"]):
            from src.security.bootloader_manager import BootloaderManager
            if not self._boot: self._boot = BootloaderManager()
            return self._boot.full_report()
        if "argos-boot-confirm" in t.upper():
            from src.security.bootloader_manager import BootloaderManager
            if not self._boot: self._boot = BootloaderManager()
            return self._boot.confirm("ARGOS-BOOT-CONFIRM")
        if any(k in t for k in ["установи persistence", "персистенс"]):
            from src.security.bootloader_manager import BootloaderManager
            if not self._boot: self._boot = BootloaderManager()
            return self._boot.install_persistence()
        if "обнови grub" in t:
            from src.security.bootloader_manager import BootloaderManager
            if not self._boot: self._boot = BootloaderManager()
            return self._boot.linux_update_grub()

        # ── Автозапуск ────────────────────────────────────
        if "установи автозапуск" in t:
            from src.security.autostart import ArgosAutostart
            return ArgosAutostart().install()
        if "статус автозапуска" in t:
            from src.security.autostart import ArgosAutostart
            return ArgosAutostart().status()
        if "удали автозапуск" in t:
            from src.security.autostart import ArgosAutostart
            return ArgosAutostart().uninstall()

        # ── P2P ───────────────────────────────────────────
        if any(k in t for k in ["статус сети", "p2p статус", "сеть нод"]):
            return self.p2p.network_status() if self.p2p else "P2P не запущен. Команда: запусти p2p"
        if "запусти p2p" in t:
            return self.start_p2p()
        if "синхронизируй навыки" in t:
            return self.p2p.sync_skills_from_network() if self.p2p else "P2P не запущен."
        if "подключись к " in t:
            ip = text.split("подключись к ")[-1].strip().split()[0]
            return self.p2p.connect_to(ip) if self.p2p else "P2P не запущен."
        if any(k in t for k in ["распредели задачу", "общая мощность"]):
            if self.p2p:
                q = text.replace("распредели задачу","").replace("общая мощность","").strip()
                return self.p2p.route_query(q or "Статус сети Аргоса.")
            return "P2P не запущен."

        # ── История ───────────────────────────────────────
        if any(k in t for k in ["история", "предыдущие разговоры"]):
            return self.db.format_history(10) if self.db else "БД не подключена."

        # ── Помощь ────────────────────────────────────────
        if t.strip() in ("помощь", "команды", "что умеешь", "help", "?"):
            return self._help()

        return None

    def _help(self) -> str:
        return """👁️ АРГОС UNIVERSAL OS — КОМАНДЫ:

📊 МОНИТОРИНГ
  статус системы · чек-ап · список процессов
  алерты · установи порог [метрика] [%] · геолокация

📁 ФАЙЛЫ  
  файлы [путь] · прочитай файл [путь]
  создай файл [имя] [текст] · удали файл [путь]

⚙️ СИСТЕМА
  консоль [команда] · убей процесс [имя]
  репликация · загрузчик · обнови grub
  установи автозапуск · веб-панель

👁️ VISION (нужен Gemini API)
  посмотри на экран · что на экране
  посмотри в камеру · анализ фото [путь]

🤖 АГЕНТ (цепочки задач)
  статус → затем крипто → потом дайджест
  отчёт агента · останови агента

🧠 ПАМЯТЬ
  запомни [ключ]: [значение] · что ты знаешь
  запиши заметку [название]: [текст]
  мои заметки · прочитай заметку [№]

⏰ РАСПИСАНИЕ
  каждые 2 часа [задача] · в 09:00 [задача]
  через 30 мин [задача] · расписание

🌐 P2P СЕТЬ
  статус сети · синхронизируй навыки
  подключись к [IP] · распредели задачу [вопрос]

🎤 ГОЛОС
  голос вкл/выкл · включи wake word

💬 ДИАЛОГ
  контекст диалога · сброс контекста
  история · помощь"""

    def load_skill(self, name: str):
        import importlib
        try:
            return importlib.import_module(f"src.skills.{name}"), f"✅ '{name}' загружен."
        except ModuleNotFoundError:
            return None, f"❌ '{name}' не найден."
