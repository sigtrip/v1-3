"""
core.py — ArgosCore FINAL v2.0
    Все подсистемы интегрированы:
    ИИ + Контекст + Голос + Wake Word + Память + Планировщик +
    Алерты + Агент + Vision + P2P + Загрузчик + 50+ команд
"""
import os, threading, requests, asyncio, tempfile
import concurrent.futures
import json
import time
import base64
import uuid
import difflib
from collections import deque

# ── Graceful imports ──────────────────────────────────────
try:
    from google import genai as genai_sdk; GEMINI_OK = True
except ImportError:
    genai_sdk = None; GEMINI_OK = False

try:
    import pyttsx3; PYTTSX3_OK = True
except ImportError:
    pyttsx3 = None; PYTTSX3_OK = False

try:
    import speech_recognition as sr; SR_OK = True
except ImportError:
    sr = None; SR_OK = False

try:
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    from ibm_watsonx_ai import Credentials
    WATSONX_OK = True
except ImportError:
    WATSONX_OK = False

from src.quantum.logic               import ArgosQuantum
from src.skills.web_scrapper         import ArgosScrapper
from src.factory.replicator          import Replicator
from src.connectivity.sensor_bridge  import ArgosSensorBridge
from src.connectivity.p2p_bridge     import ArgosBridge, p2p_protocol_roadmap
from src.skill_loader                import SkillLoader
from src.dag_agent                   import DAGManager
from src.github_marketplace          import GitHubMarketplace
from src.modules                     import ModuleLoader
from src.context_manager             import DialogContext
from src.agent                       import ArgosAgent
from src.argos_logger                import get_logger
from src.env_bootstrap               import bootstrap_env
bootstrap_env()

log = get_logger("argos.core")


class _SlidingWindowRateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._hits = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = time.time()
        with self._lock:
            while self._hits and (now - self._hits[0]) >= self.window_seconds:
                self._hits.popleft()
            if len(self._hits) >= self.max_calls:
                return False
            self._hits.append(now)
            return True


class _GeminiResponse:
    def __init__(self, text: str = ""):
        self.text = text or ""


class _GeminiCompatClient:
    """Лёгкий адаптер google.genai под старый интерфейс generate_content()."""
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        self.client = genai_sdk.Client(api_key=api_key)
        self.model_name = self._resolve_model_name(model_name)

    def _resolve_model_name(self, requested: str) -> str:
        env_model = os.getenv("GEMINI_MODEL", "").strip()
        if env_model:
            requested = env_model

        candidates = [
            requested,
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]

        try:
            available = []
            for model in self.client.models.list():
                name = getattr(model, "name", "") or ""
                if name:
                    available.append(name)

            if not available:
                return requested

            for cand in candidates:
                if cand in available:
                    return cand
                if f"models/{cand}" in available:
                    return f"models/{cand}"

            # Берём первую flash-модель, если есть
            for name in available:
                if "flash" in name.lower():
                    return name
            return available[0]
        except Exception:
            return requested

    def generate_content(self, contents):
        if isinstance(contents, list):
            prompt = "\n\n".join(str(x) for x in contents if isinstance(x, str) and x.strip())
        else:
            prompt = str(contents)
        try:
            resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
        except Exception as first_error:
            # Попытка один раз переключиться на доступную модель (404/NOT_FOUND и совместимость API)
            new_model = self._resolve_model_name("gemini-2.0-flash")
            if new_model != self.model_name:
                self.model_name = new_model
                resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
            else:
                raise first_error

        text = getattr(resp, "text", "") or ""
        return _GeminiResponse(text=text)


class ArgosCore:
    def __init__(self):
        self.quantum    = ArgosQuantum()
        self.scrapper   = ArgosScrapper()
        self.replicator = Replicator()
        self.sensors    = ArgosSensorBridge()
        self.context    = DialogContext(max_turns=10)
        self.agent      = ArgosAgent(self)
        self.ollama_url = "http://localhost:11434/api/generate"
        self.lmstudio_url = (os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1/chat/completions") or "").strip()
        self.lmstudio_model = (os.getenv("LMSTUDIO_MODEL", "local-model") or "").strip() or "local-model"
        self.ai_mode    = self._normalize_ai_mode(os.getenv("ARGOS_AI_MODE", "auto"))
        self.voice_on   = os.getenv("ARGOS_VOICE_DEFAULT", "off").strip().lower() in (
            "1", "true", "on", "yes", "да", "вкл"
        )
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
        self._whisper_model = None
        self.skill_loader = None
        self.dag_manager  = None
        self.marketplace  = None
        self.iot_bridge   = None
        self.mesh_net     = None
        self.smart_sys    = None
        self.gateway_mgr  = None
        self.smart_profiles = {}
        self._smart_create_wizard = None
        self.operator_mode = False
        self.module_loader = None
        self.ha = None
        self.nfc = None
        self.usb_diag = None
        self.bt_scanner = None
        self.tool_calling = None
        self.git_ops = None
        self.task_queue = None
        self.awa = None
        self.drafter = None
        self.healer = None
        self.air_snitch = None
        self.wifi_sentinel = None
        self.smarthome = None
        self.power_sentry = None
        self.purge = None
        self.containers = None
        self.master_auth = None
        self.biosphere_dag = None
        self._runtime_admin = None
        self._runtime_flasher = None
        self.gemini_rpm_limit = 15
        self._gemini_limiter = _SlidingWindowRateLimiter(max_calls=self.gemini_rpm_limit, window_seconds=60)
        self._last_gemini_rate_limited = False
        self._gigachat_access_token = (os.getenv("GIGACHAT_ACCESS_TOKEN", "") or "").strip() or None
        self._gigachat_token_expires_at = 0.0
        self.auto_collab_enabled = os.getenv("ARGOS_AUTO_COLLAB", "on").strip().lower() not in {"0", "false", "off", "no", "нет"}
        self.auto_collab_max_models = max(2, min(int(os.getenv("ARGOS_AUTO_COLLAB_MAX_MODELS", "4") or "4"), 4))
        self.spec_draft_count = max(1, min(int(os.getenv("ARGOS_SPEC_DRAFT_COUNT", "3") or "3"), 3))
        try:
            self.acceptance_major_ratio = max(0.4, min(float(os.getenv("ARGOS_ACCEPTANCE_MAJOR_RATIO", "0.72") or "0.72"), 0.95))
        except Exception:
            self.acceptance_major_ratio = 0.72
        self.homeostasis = None
        self.curiosity = None
        self._homeostasis_block_heavy = False

        self._init_voice()
        self._setup_ai()
        self._setup_watsonx()
        self._init_memory()
        self._init_homeostasis()
        self._init_curiosity()
        self._init_scheduler()
        self._init_alerts()
        self._init_vision()
        self._init_skills()
        self._init_dags()
        self._init_marketplace()
        self._init_iot()
        self._init_smart_systems()
        self._init_home_assistant()
        self._init_nfc()
        self._init_usb_diagnostics()
        self._init_bluetooth()
        self._init_awa_core()
        self._init_adaptive_drafter()
        self._init_self_healing()
        self._init_air_snitch()
        self._init_wifi_sentinel()
        self._init_smarthome_override()
        self._init_power_sentry()
        self._init_emergency_purge()
        self._init_container_isolation()
        self._init_master_auth()
        self._init_biosphere_dag()
        self._init_modules()
        self._init_tool_calling()
        self._init_git_ops()
        self._init_task_queue()
        log.info("ArgosCore FINAL v2.0 инициализирован.")

    # ═══════════════════════════════════════════════════════
    # ИНИЦИАЛИЗАЦИЯ ПОДСИСТЕМ
    # ═══════════════════════════════════════════════════════
    def _init_memory(self):
        try:
            from src.memory import ArgosMemory
            self.memory = ArgosMemory()
            self.context.memory_ref = self.memory
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

    def _init_homeostasis(self):
        try:
            from src.hardware_guard import HardwareHomeostasisGuard
            self.homeostasis = HardwareHomeostasisGuard(core=self)
            if os.getenv("ARGOS_HOMEOSTASIS", "on").strip().lower() not in {"0", "off", "false", "no", "нет"}:
                self.homeostasis.start()
            log.info("Homeostasis: OK")
        except Exception as e:
            log.warning("Homeostasis: %s", e)

    def _init_curiosity(self):
        try:
            from src.curiosity import ArgosCuriosity
            self.curiosity = ArgosCuriosity(core=self)
            if os.getenv("ARGOS_CURIOSITY", "on").strip().lower() not in {"0", "off", "false", "no", "нет"}:
                self.curiosity.start()
            log.info("Curiosity: OK")
        except Exception as e:
            log.warning("Curiosity: %s", e)

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

    def _init_skills(self):
        try:
            self.skill_loader = SkillLoader()
            report = self.skill_loader.load_all(core=self)
            log.info("SkillLoader: OK")
            log.info(report.replace("\n", " | "))
        except Exception as e:
            log.warning("SkillLoader: %s", e)

    def _init_dags(self):
        try:
            self.dag_manager = DAGManager(core=self)
            log.info("DAG Manager: OK")
        except Exception as e:
            log.warning("DAG Manager: %s", e)

    def _init_marketplace(self):
        try:
            self.marketplace = GitHubMarketplace(skill_loader=self.skill_loader, core=self)
            log.info("GitHub Marketplace: OK")
        except Exception as e:
            log.warning("GitHub Marketplace: %s", e)

    def _init_iot(self):
        """IoT Bridge + Mesh Network + Gateway Manager."""
        try:
            from src.connectivity.iot_bridge import IoTBridge
            self.iot_bridge = IoTBridge()
            log.info("IoT Bridge: OK (%d устройств)", len(self.iot_bridge.registry.all()))
        except Exception as e:
            log.warning("IoT Bridge: %s", e)

        try:
            from src.connectivity.mesh_network import MeshNetwork
            self.mesh_net = MeshNetwork()
            log.info("Mesh Network: OK (%d устройств)", len(self.mesh_net.devices))
        except Exception as e:
            log.warning("Mesh Network: %s", e)

        try:
            from src.connectivity.gateway_manager import GatewayManager
            self.gateway_mgr = GatewayManager(iot_bridge=self.iot_bridge)
            log.info("Gateway Manager: OK")
        except Exception as e:
            log.warning("Gateway Manager: %s", e)

    def _init_smart_systems(self):
        """Smart Systems Manager — умные среды + DAG Bio-Control."""
        try:
            from src.smart_systems import SmartSystemsManager, SYSTEM_PROFILES
            self.smart_sys = SmartSystemsManager(on_alert=self._on_alert)
            self.smart_profiles = SYSTEM_PROFILES
            log.info("Smart Systems: OK (%d систем)", len(self.smart_sys.systems))
        except Exception as e:
            log.warning("Smart Systems: %s", e)

    def _init_modules(self):
        """Dynamic modules (src/modules/*_module.py)."""
        try:
            self.module_loader = ModuleLoader()
            report = self.module_loader.load_all(core=self)
            log.info(report.replace("\n", " | "))
        except Exception as e:
            log.warning("Modules: %s", e)

    def _init_home_assistant(self):
        try:
            from src.connectivity.home_assistant import HomeAssistantBridge
            self.ha = HomeAssistantBridge()
            log.info("Home Assistant bridge: %s", "ON" if self.ha.enabled else "OFF")
        except Exception as e:
            log.warning("Home Assistant bridge: %s", e)

    def _init_nfc(self):
        """NFC Manager — мониторинг собственных NFC-меток."""
        try:
            from src.connectivity.nfc_manager import NFCManager
            self.nfc = NFCManager(android_mode=False)
            log.info("NFC Manager: OK (%d меток)", len(self.nfc.list_tags()))
        except Exception as e:
            log.warning("NFC Manager: %s", e)

    def _init_usb_diagnostics(self):
        """USB Diagnostics — диагностика авторизованных устройств."""
        try:
            from src.connectivity.usb_diagnostics import USBDiagnostics
            self.usb_diag = USBDiagnostics(android_mode=False)
            log.info("USB Diagnostics: OK (%d авториз.)", len(self.usb_diag.list_authorized()))
        except Exception as e:
            log.warning("USB Diagnostics: %s", e)

    def _init_bluetooth(self):
        """Bluetooth Scanner — инвентаризация IoT."""
        try:
            from src.connectivity.bluetooth_scanner import ArgosBluetoothScanner
            self.bt_scanner = ArgosBluetoothScanner()
            log.info("BT Scanner: OK (%d в инвентаре)", len(self.bt_scanner.devices))
        except Exception as e:
            log.warning("BT Scanner: %s", e)

    def _init_awa_core(self):
        """AWA-Core — центральный координатор модулей."""
        try:
            from src.awa_core import AWACore
            self.awa = AWACore(core=self)
            log.info("AWA-Core: OK")
        except Exception as e:
            log.warning("AWA-Core: %s", e)

    def _init_adaptive_drafter(self):
        """Adaptive Drafter (TLT) — кэш/сжатие/фильтрация."""
        try:
            from src.adaptive_drafter import AdaptiveDrafter
            self.drafter = AdaptiveDrafter(core=self)
            log.info("Adaptive Drafter: OK")
        except Exception as e:
            log.warning("Adaptive Drafter: %s", e)

    def _init_self_healing(self):
        """Self-Healing Engine — автоисправление Python-кода."""
        try:
            from src.self_healing import SelfHealingEngine
            self.healer = SelfHealingEngine(core=self)
            self.healer.start_intercepting()
            log.info("Self-Healing: OK")
        except Exception as e:
            log.warning("Self-Healing: %s", e)

    def _init_air_snitch(self):
        """AirSnitch — SDR/Sub-GHz сканер эфира."""
        try:
            from src.connectivity.air_snitch import AirSnitch
            self.air_snitch = AirSnitch()
            log.info("AirSnitch: OK (backend=%s)", self.air_snitch.backend)
        except Exception as e:
            log.warning("AirSnitch: %s", e)

    def _init_wifi_sentinel(self):
        """WiFi Sentinel — сетевая безопасность + HoneyPot."""
        try:
            from src.connectivity.wifi_sentinel import WiFiSentinel
            self.wifi_sentinel = WiFiSentinel(core=self)
            log.info("WiFi Sentinel: OK")
        except Exception as e:
            log.warning("WiFi Sentinel: %s", e)

    def _init_smarthome_override(self):
        """SmartHome Override — прямое управление Zigbee/Z-Wave."""
        try:
            from src.connectivity.smarthome_override import SmartHomeOverride
            self.smarthome = SmartHomeOverride()
            log.info("SmartHome Override: OK (%d устройств)", len(self.smarthome.devices))
        except Exception as e:
            log.warning("SmartHome Override: %s", e)

    def _init_power_sentry(self):
        """Power Sentry — контроль энергосистемы / UPS."""
        try:
            from src.connectivity.power_sentry import PowerSentry
            self.power_sentry = PowerSentry()
            log.info("Power Sentry: OK")
        except Exception as e:
            log.warning("Power Sentry: %s", e)

    def _init_emergency_purge(self):
        """Emergency Purge — экстренное уничтожение данных."""
        try:
            from src.security.emergency_purge import EmergencyPurge
            self.purge = EmergencyPurge()
            log.info("Emergency Purge: OK")
        except Exception as e:
            log.warning("Emergency Purge: %s", e)

    def _init_container_isolation(self):
        """Container Isolation — LXD/Docker изоляция."""
        try:
            from src.security.container_isolation import ContainerIsolation
            self.containers = ContainerIsolation()
            log.info("Container Isolation: OK (runtime=%s)", self.containers.runtime.value)
        except Exception as e:
            log.warning("Container Isolation: %s", e)

    def _init_master_auth(self):
        """MasterKeyValidator — авторизация администратора."""
        try:
            from src.security.master_auth import get_auth
            self.master_auth = get_auth()
            log.info("Master Auth: %s", "configured" if self.master_auth.is_configured else "pass-through")
        except Exception as e:
            log.warning("Master Auth: %s", e)

    def _init_biosphere_dag(self):
        """BiosphereDAG — DAG-контроллер биосферы."""
        try:
            from src.modules.biosphere_dag import BiosphereDAG
            env = os.getenv("ARGOS_BIOSPHERE_ENV", "generic").strip().lower()
            self.biosphere_dag = BiosphereDAG(environment=env)
            # Подключаем к idle-циклу если есть task_queue
            if self.task_queue:
                self.task_queue.register_idle_learning_handler(self.biosphere_dag.run_cycle)
            log.info("BiosphereDAG: OK (env=%s)", env)
        except Exception as e:
            log.warning("BiosphereDAG: %s", e)

    def _init_tool_calling(self):
        try:
            from src.tool_calling import ArgosToolCallingEngine
            self.tool_calling = ArgosToolCallingEngine(core=self)
            log.info("Tool Calling: OK")
        except Exception as e:
            log.warning("Tool Calling: %s", e)

    def _init_git_ops(self):
        try:
            from src.git_ops import ArgosGitOps
            self.git_ops = ArgosGitOps(repo_path=".")
            log.info("GitOps: OK")
        except Exception as e:
            log.warning("GitOps: %s", e)

    def _init_task_queue(self):
        try:
            from src.task_queue import TaskQueueManager
            self.task_queue = TaskQueueManager(worker_count=2)
            self.task_queue.register_runner("logic.command", self._queue_run_logic)
            if self.curiosity and hasattr(self.curiosity, "run_idle_learning_cycle"):
                self.task_queue.register_idle_learning_handler(self.curiosity.run_idle_learning_cycle)
            if self.biosphere_dag and hasattr(self.biosphere_dag, "run_cycle"):
                self.task_queue.register_idle_learning_handler(self.biosphere_dag.run_cycle)
            self.task_queue.start()
            log.info("TaskQueue: OK")
        except Exception as e:
            log.warning("TaskQueue: %s", e)

    def _queue_run_logic(self, task) -> str:
        command = str(task.payload.get("command", "") or "").strip()
        if not command:
            return "Пустая queued-команда"
        if not self._runtime_admin or not self._runtime_flasher:
            return "Runtime контекст недоступен для очереди (admin/flasher не инициализированы)."
        result = self.process_logic(command, self._runtime_admin, self._runtime_flasher)
        if isinstance(result, dict):
            return str(result.get("answer", ""))
        return str(result)

    def _classify_queue_command(self, command: str) -> str:
        cmd = (command or "").lower()
        heavy_markers = [
            "посмотри на экран", "что на экране", "посмотри в камеру", "анализ фото",
            "проанализируй изображение", "компиля", "compile", "создай прошивку", "прошей",
        ]
        iot_markers = [
            "шлюз", "gateway", "датчик", "sensor", "mqtt", "zigbee", "lora", "mesh", "ha ",
            "home assistant", "iot",
        ]
        system_markers = [
            "git ", "гит ", "очередь ", "queue ", "статус системы", "чек-ап", "список процессов",
            "файлы", "прочитай файл", "создай файл", "удали файл", "консоль ", "оператор ",
        ]
        if any(marker in cmd for marker in heavy_markers):
            return "heavy"
        if any(marker in cmd for marker in iot_markers):
            return "iot"
        if any(marker in cmd for marker in system_markers):
            return "system"
        return "ai"

    def _on_alert(self, msg: str):
        log.warning("ALERT: %s", msg)
        self.say(msg)

    def _remember_dialog_turn(self, user_text: str, answer: str, state: str):
        if not self.memory:
            return
        try:
            self.memory.log_dialogue("user", user_text, state=state)
            self.memory.log_dialogue("argos", answer, state=state)
        except Exception as e:
            log.warning("Memory dialogue index: %s", e)

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
            from src.interface.fastapi_dashboard import FastAPIDashboard
            self._dashboard = FastAPIDashboard(self, admin, flasher, port)
            result = self._dashboard.start()
            if isinstance(result, str) and not result.startswith("❌"):
                return result
        except Exception:
            pass

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
            except Exception as e:
                log.warning("TTS runtime error: %s", e)
        threading.Thread(target=_speak, daemon=True).start()

    def listen(self) -> str:
        if SR_OK:
            try:
                rec = sr.Recognizer()
                with sr.Microphone() as src:
                    log.info("Слушаю...")
                    rec.adjust_for_ambient_noise(src, duration=0.5)
                    audio = rec.listen(src, timeout=7, phrase_time_limit=15)
                    try:
                        text = rec.recognize_google(audio, language="ru-RU")
                        log.info("Распознано (google): %s", text)
                        return text.lower()
                    except Exception:
                        text = self._transcribe_with_whisper(audio)
                        if text:
                            log.info("Распознано (whisper): %s", text)
                            return text.lower()
            except Exception as e:
                log.error("STT: %s", e)

        log.warning("STT недоступен (SpeechRecognition/Whisper)")
        return ""

    def _transcribe_with_whisper(self, audio_data) -> str:
        try:
            if self._whisper_model is None:
                from faster_whisper import WhisperModel
                model_size = os.getenv("WHISPER_MODEL", "small")
                device = os.getenv("WHISPER_DEVICE", "cpu")
                compute = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
                self._whisper_model = WhisperModel(model_size, device=device, compute_type=compute)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_data.get_wav_data())
                wav_path = tmp.name

            segments, _ = self._whisper_model.transcribe(wav_path, language="ru", vad_filter=True)
            text = " ".join(seg.text.strip() for seg in segments if seg.text and seg.text.strip())
            try:
                os.remove(wav_path)
            except Exception:
                pass
            return text
        except Exception as e:
            log.warning("Whisper STT fallback: %s", e)
            return ""

    def transcribe_audio_path(self, audio_path: str) -> str:
        """Транскрибация аудиофайла (ogg/mp3/wav) через faster-whisper."""
        if not audio_path or not os.path.exists(audio_path):
            return ""
        try:
            if self._whisper_model is None:
                from faster_whisper import WhisperModel
                model_size = os.getenv("WHISPER_MODEL", "small")
                device = os.getenv("WHISPER_DEVICE", "cpu")
                compute = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
                self._whisper_model = WhisperModel(model_size, device=device, compute_type=compute)

            segments, _ = self._whisper_model.transcribe(audio_path, language="ru", vad_filter=True)
            text = " ".join(seg.text.strip() for seg in segments if seg.text and seg.text.strip())
            return text.strip()
        except Exception as e:
            log.warning("Whisper file STT: %s", e)
            return ""

    # ═══════════════════════════════════════════════════════
    # ИИ
    # ═══════════════════════════════════════════════════════
    def _normalize_ai_mode(self, mode: str) -> str:
        value = (mode or "auto").strip().lower()
        canonical = value.replace(" ", "").replace("-", "")
        if value in {"gemini", "google", "g"}:
            return "gemini"
        if value in {"gigachat", "giga", "sber", "gc"}:
            return "gigachat"
        if value in {"yandexgpt", "yandex", "ya", "yg"}:
            return "yandexgpt"
        if canonical in {"lmstudio", "lm", "lms", "studio"}:
            return "lmstudio"
        if value in {"ollama", "local", "o"}:
            return "ollama"
        if value in {"watson", "watsonx", "ibm", "w"}:
            return "watsonx"
        return "auto"

    def set_ai_mode(self, mode: str) -> str:
        self.ai_mode = self._normalize_ai_mode(mode)
        return f"🤖 Режим ИИ: {self.ai_mode_label()}"

    def ai_mode_label(self) -> str:
        if self.ai_mode == "gemini":
            return "Gemini"
        if self.ai_mode == "gigachat":
            return "GigaChat"
        if self.ai_mode == "yandexgpt":
            return "YandexGPT"
        if self.ai_mode == "lmstudio":
            return "LM Studio"
        if self.ai_mode == "ollama":
            return "Ollama"
        if self.ai_mode == "watsonx":
            return "Watsonx"
        return "Auto"

    def _setup_ai(self):
        key = os.getenv("GEMINI_API_KEY", "")
        if GEMINI_OK and key and key != "your_key_here":
            self.model = _GeminiCompatClient(api_key=key, model_name="gemini-2.0-flash")
            log.info("Gemini: OK")
        else:
            self.model = None
            log.info("Gemini недоступен — используется Ollama")

        if self._has_gigachat_config():
            log.info("GigaChat: конфигурация обнаружена")
        else:
            log.info("GigaChat недоступен — нет credentials")

        if self._has_yandexgpt_config():
            log.info("YandexGPT: конфигурация обнаружена")
        else:
            log.info("YandexGPT недоступен — нет IAM/FOLDER")

        if self._has_lmstudio_config():
            log.info("LM Studio: конфигурация обнаружена (%s)", self.lmstudio_url)
        else:
            log.info("LM Studio недоступен — нет BASE_URL")

    def _setup_watsonx(self):
        """IBM Watsonx AI — Llama-3 70B через инфраструктуру IBM."""
        self.watsonx_api_key = (os.getenv("WATSONX_API_KEY", "") or "").strip()
        self.watsonx_project_id = (os.getenv("WATSONX_PROJECT_ID", "") or "").strip()
        self.watsonx_url = (os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com") or "").strip()
        self.watsonx_model = None

        if WATSONX_OK and self.watsonx_api_key and self.watsonx_project_id:
            try:
                credentials = Credentials(
                    api_key=self.watsonx_api_key,
                    url=self.watsonx_url
                )
                parameters = {
                    GenParams.DECODING_METHOD: "greedy",
                    GenParams.MAX_NEW_TOKENS: 1024,
                    GenParams.REPETITION_PENALTY: 1.05
                }
                self.watsonx_model = ModelInference(
                    model_id="meta-llama/llama-3-1-70b-instruct",
                    params=parameters,
                    credentials=credentials,
                    project_id=self.watsonx_project_id
                )
                log.info("Watsonx: OK (Llama-3.1-70B)")
            except Exception as e:
                log.warning("Watsonx недоступен: %s", e)
        else:
            log.info("Watsonx: отключён (pip install ibm-watsonx-ai + ключи в .env)")

    def _gemini_rate_limit_text(self) -> str:
        return f"Gemini: превышен лимит {self.gemini_rpm_limit} запросов в минуту. Повтори чуть позже или переключи режим ИИ."

    def _has_gigachat_config(self) -> bool:
        if self._gigachat_access_token:
            return True
        client_id = (os.getenv("GIGACHAT_CLIENT_ID", "") or "").strip()
        client_secret = (os.getenv("GIGACHAT_CLIENT_SECRET", "") or "").strip()
        return bool(client_id and client_secret)

    def _has_yandexgpt_config(self) -> bool:
        iam = (os.getenv("YANDEX_IAM_TOKEN", "") or "").strip()
        folder = (os.getenv("YANDEX_FOLDER_ID", "") or "").strip()
        return bool(iam and folder)

    def _has_lmstudio_config(self) -> bool:
        return bool((self.lmstudio_url or "").strip())

    def _lmstudio_status(self) -> str:
        if not self._has_lmstudio_config():
            return "❌ LM Studio не настроен. Укажи LMSTUDIO_BASE_URL и LMSTUDIO_MODEL в .env"
        try:
            payload = {
                "model": self.lmstudio_model,
                "messages": [{"role": "user", "content": "ping"}],
                "temperature": 0.0,
                "max_tokens": 4,
                "stream": False,
            }
            response = requests.post(self.lmstudio_url, json=payload, timeout=8)
            if response.ok:
                return (
                    "🧪 LM Studio: ONLINE\n"
                    f"  URL: {self.lmstudio_url}\n"
                    f"  Model: {self.lmstudio_model}"
                )
            return (
                "⚠️ LM Studio: OFFLINE/ERROR\n"
                f"  URL: {self.lmstudio_url}\n"
                f"  HTTP: {response.status_code}\n"
                f"  Body: {(response.text or '')[:180]}"
            )
        except Exception as e:
            return (
                "⚠️ LM Studio: недоступен\n"
                f"  URL: {self.lmstudio_url}\n"
                f"  Error: {e}"
            )

    def _get_gigachat_token(self) -> str | None:
        if self._gigachat_access_token and self._gigachat_token_expires_at <= 0:
            return self._gigachat_access_token

        if self._gigachat_access_token and time.time() < self._gigachat_token_expires_at - 30:
            return self._gigachat_access_token

        client_id = (os.getenv("GIGACHAT_CLIENT_ID", "") or "").strip()
        client_secret = (os.getenv("GIGACHAT_CLIENT_SECRET", "") or "").strip()
        if not (client_id and client_secret):
            return self._gigachat_access_token

        try:
            basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
            headers = {
                "Authorization": f"Basic {basic}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            response = requests.post(
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                headers=headers,
                data={"scope": "GIGACHAT_API_PERS"},
                timeout=20,
            )
            if not response.ok:
                log.error("GigaChat auth: HTTP %s %s", response.status_code, response.text[:400])
                return None

            payload = response.json()
            token = (payload.get("access_token") or "").strip()
            if not token:
                return None

            expires_at_ms = payload.get("expires_at")
            if isinstance(expires_at_ms, (int, float)):
                self._gigachat_token_expires_at = float(expires_at_ms) / 1000.0
            else:
                self._gigachat_token_expires_at = time.time() + 1800

            self._gigachat_access_token = token
            return token
        except Exception as e:
            log.error("GigaChat auth error: %s", e)
            return None

    def _ask_gemini(self, context: str, user_text: str) -> str | None:
        self._last_gemini_rate_limited = False
        if not self.model:
            return None
        if not self._gemini_limiter.allow():
            self._last_gemini_rate_limited = True
            log.warning(self._gemini_rate_limit_text())
            return None
        try:
            hist = self.context.get_prompt_context()
            payload = f"{context}\n\n{hist}\n\nUser: {user_text}\nArgos:"
            res = self.model.generate_content(payload)
            return res.text
        except Exception as e:
            log.error("Gemini: %s", e)
            return None

    def _ask_gigachat(self, context: str, user_text: str) -> str | None:
        token = self._get_gigachat_token()
        if not token:
            return None
        try:
            hist = self.context.get_prompt_context()
            payload = {
                "model": (os.getenv("GIGACHAT_MODEL", "GigaChat-2") or "GigaChat-2").strip(),
                "messages": [
                    {"role": "system", "content": context},
                    {"role": "user", "content": f"{hist}\n\n{user_text}"},
                ],
                "temperature": 0.4,
                "max_tokens": 1200,
            }
            response = requests.post(
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=payload,
                timeout=25,
            )
            if not response.ok:
                log.error("GigaChat: HTTP %s %s", response.status_code, response.text[:400])
                return None

            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            return None
        except Exception as e:
            log.error("GigaChat: %s", e)
            return None

    def _ask_yandexgpt(self, context: str, user_text: str) -> str | None:
        iam = (os.getenv("YANDEX_IAM_TOKEN", "") or "").strip()
        folder = (os.getenv("YANDEX_FOLDER_ID", "") or "").strip()
        if not (iam and folder):
            return None

        model_uri = (os.getenv("YANDEXGPT_MODEL_URI", "") or "").strip()
        if not model_uri:
            model_uri = f"gpt://{folder}/yandexgpt-lite/latest"

        try:
            hist = self.context.get_prompt_context()
            payload = {
                "modelUri": model_uri,
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.4,
                    "maxTokens": "1200",
                },
                "messages": [
                    {"role": "system", "text": context},
                    {"role": "user", "text": f"{hist}\n\n{user_text}"},
                ],
            }
            response = requests.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                headers={
                    "Authorization": f"Bearer {iam}",
                    "x-folder-id": folder,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=25,
            )
            if not response.ok:
                log.error("YandexGPT: HTTP %s %s", response.status_code, response.text[:400])
                return None

            data = response.json()
            result = data.get("result") or {}
            alternatives = result.get("alternatives") or []
            if not alternatives:
                return None
            message = alternatives[0].get("message") or {}
            text = message.get("text")
            if isinstance(text, str):
                return text.strip()
            return None
        except Exception as e:
            log.error("YandexGPT: %s", e)
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

    def _ask_lmstudio(self, context: str, user_text: str) -> str | None:
        if not self._has_lmstudio_config():
            return None
        try:
            hist = self.context.get_prompt_context()
            payload = {
                "model": self.lmstudio_model,
                "messages": [
                    {"role": "system", "content": context},
                    {"role": "user", "content": f"{hist}\n\n{user_text}"},
                ],
                "temperature": 0.4,
                "max_tokens": 1200,
                "stream": False,
            }
            response = requests.post(
                self.lmstudio_url,
                json=payload,
                timeout=25,
            )
            if not response.ok:
                log.error("LM Studio: HTTP %s %s", response.status_code, response.text[:400])
                return None

            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            return None
        except Exception as e:
            log.error("LM Studio: %s", e)
            return None

    def _ask_watsonx(self, context: str, user_text: str) -> str | None:
        if not self.watsonx_model:
            return None
        try:
            hist = self.context.get_prompt_context()
            full_prompt = (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
                f"{context}\n<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n"
                f"{hist}\nUser: {user_text}\n<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n"
            )
            res = self.watsonx_model.generate_text(prompt=full_prompt)
            return res.strip() if res else None
        except Exception as e:
            log.error("Watsonx: %s", e)
            return None

    def _ask_consensus(self, context: str, user_text: str) -> str | None:
        """
        Speculative Consensus v2:
        Параллельно опрашивает все доступные ядра (Drafters),
        затем использует Verifier для синтеза единого ответа.
        """
        drafts = {}
        log.info("⚛️ Запуск консенсуса моделей...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            if self.model:
                futures[executor.submit(self._ask_gemini, context, user_text)] = "Gemini"
            if getattr(self, "watsonx_model", None):
                futures[executor.submit(self._ask_watsonx, context, user_text)] = "Watsonx"
            if self.ollama_url:
                futures[executor.submit(self._ask_ollama, context, user_text)] = "Ollama"

            for future in concurrent.futures.as_completed(futures):
                model_name = futures[future]
                try:
                    res = future.result()
                    if res:
                        drafts[model_name] = res
                        log.info("Drafter [%s] готов.", model_name)
                except Exception as e:
                    log.warning("Ошибка Drafter-а [%s]: %s", model_name, e)

        if not drafts:
            return None

        if len(drafts) == 1:
            return list(drafts.values())[0]

        log.info("🧠 Синтез финального ответа (Verifier)...")
        verifier_context = (
            f"{context}\n\n"
            "СИСТЕМНОЕ ЗАДАНИЕ: Ты — Verifier (Синтезатор) ОС Аргос. "
            "Ниже представлены черновики ответов от разных нейросетевых ядер на запрос пользователя. "
            "Твоя задача — проанализировать их, убрать противоречия, взять лучшие факты из каждого "
            "и сформировать единый, краткий и точный ответ."
        )

        drafts_text = "\n\n".join([f"--- Вариант от {name} ---\n{text}" for name, text in drafts.items()])
        verifier_prompt = f"Запрос пользователя: {user_text}\n\n{drafts_text}\n\nФинальный ответ Аргоса:"

        final_answer = None
        if getattr(self, "watsonx_model", None):
            final_answer = self._ask_watsonx(verifier_context, verifier_prompt)
        elif self.model:
            final_answer = self._ask_gemini(verifier_context, verifier_prompt)

        if not final_answer:
            return list(drafts.values())[0]

        return final_answer

    def _local_drafter_providers(self) -> list[tuple[str, callable]]:
        providers = []
        if self._has_lmstudio_config():
            providers.append(("LMStudio", self._ask_lmstudio))
        providers.append(("Ollama", self._ask_ollama))
        return providers[:self.auto_collab_max_models]

    def _cloud_verifier_providers(self) -> list[tuple[str, callable]]:
        providers = []
        if self.model:
            providers.append(("Gemini", self._ask_gemini))
        if self._has_gigachat_config():
            providers.append(("GigaChat", self._ask_gigachat))
        return providers[:self.auto_collab_max_models]

    def _all_auto_providers(self) -> list[tuple[str, callable]]:
        return self._cloud_verifier_providers() + self._local_drafter_providers()

    def _post_verifier_feedback(self, user_text: str, drafts: list[tuple[str, str]], final_answer: str, verifier: str):
        """Per-drafter quality tracking + curiosity alignment."""
        if not drafts or not final_answer:
            return
        best_ratio = 0.0
        best_drafter = "unknown"
        drafter_scores: list[tuple[str, float]] = []
        for drafter_name, draft_text in drafts:
            ratio = difflib.SequenceMatcher(None, (draft_text or "").strip(), (final_answer or "").strip()).ratio()
            drafter_scores.append((drafter_name, ratio))
            if ratio >= best_ratio:
                best_ratio = ratio
                best_drafter = drafter_name
        accepted = best_ratio >= self.acceptance_major_ratio
        try:
            from src.observability import record_acceptance
            record_acceptance(
                accepted=accepted,
                drafter=best_drafter,
                verifier=verifier,
                similarity=best_ratio,
            )
            # Per-drafter quality → отдельные метрики
            from src.observability import Metrics as ObsMetrics
            for d_name, d_ratio in drafter_scores:
                ObsMetrics.observe("drafter.similarity", d_ratio, tags={"drafter": d_name})
                ObsMetrics.gauge(f"drafter.last_similarity.{d_name}", d_ratio)
        except Exception:
            pass

        if self.curiosity and hasattr(self.curiosity, "ingest_verifier_lesson"):
            try:
                self.curiosity.ingest_verifier_lesson(
                    prompt=user_text,
                    drafts=drafts,
                    final_answer=final_answer,
                    verifier=verifier,
                    accepted=accepted,
                    similarity=best_ratio,
                )
            except Exception as e:
                log.warning("Curiosity verifier lesson: %s", e)

    def _ask_auto_consensus(self, context: str, user_text: str) -> tuple[str | None, str | None]:
        """
        Speculative Consensus v2:
          1. Локальные модели (Ollama/LM Studio) = Drafter-каста → генерируют N черновиков ПАРАЛЛЕЛЬНО
          2. Облачная модель (Gemini/GigaChat) = Verifier-каста → НЕ пишет с нуля,
             а ищет ошибки в черновиках и собирает финал
          3. Per-drafter quality tracking через acceptance_rate
        """
        providers = self._all_auto_providers()
        if not providers:
            return None, None

        if not self.auto_collab_enabled:
            for provider_name, fn in providers:
                answer = fn(context, user_text)
                if answer:
                    return answer, provider_name
            return None, None

        drafters = self._local_drafter_providers()
        verifiers = self._cloud_verifier_providers()

        # ── Параллельная генерация черновиков ──────────────
        drafts: list[tuple[str, str]] = []
        if drafters:
            draft_slots: list[dict] = []
            for idx in range(self.spec_draft_count):
                provider_name, fn = drafters[idx % len(drafters)]
                draft_slots.append({"idx": idx, "name": provider_name, "fn": fn, "result": None})

            def _gen_draft(slot: dict):
                try:
                    draft_prompt = (
                        f"Сделай быстрый ЧЕРНОВИК #{slot['idx'] + 1} для запроса пользователя. "
                        "Коротко, по делу, без лишних пояснений."
                        " Если это код — дай рабочий скелет без длинных вступлений.\n\n"
                        f"Запрос пользователя: {user_text}"
                    )
                    answer = slot["fn"](
                        context + "\n\nРоль: Drafter. Только быстрый черновик.",
                        draft_prompt,
                    )
                    slot["result"] = answer.strip() if answer else None
                except Exception as exc:
                    log.debug("Drafter %s draft#%d error: %s", slot["name"], slot["idx"], exc)

            threads = []
            for slot in draft_slots:
                t = threading.Thread(target=_gen_draft, args=(slot,), daemon=True)
                threads.append(t)
                t.start()
            for t in threads:
                t.join(timeout=30)

            for slot in draft_slots:
                if slot["result"]:
                    drafts.append((slot["name"], slot["result"]))

        if not drafts:
            for provider_name, fn in providers:
                answer = fn(context, user_text)
                if answer and answer.strip():
                    return answer.strip(), provider_name
            return None, None

        if not verifiers:
            return drafts[0][1], f"SpecConsensus:DraftOnly({drafts[0][0]})"

        # ── Верификация ───────────────────────────────────
        drafts_block = "\n\n".join(
            f"=== ЧЕРНОВИК #{i+1} (от {name}) ===\n{text}"
            for i, (name, text) in enumerate(drafts)
        )
        verifier_prompt = (
            "Ты Verifier. АБСОЛЮТНЫЙ ЗАПРЕТ писать ответ с нуля.\n"
            "Алгоритм:\n"
            "  1. Прочитай все черновики.\n"
            "  2. Перечисли найденные ошибки (фактология, логика, код) — одной строкой на ошибку.\n"
            "  3. Выбери лучший черновик как основу.\n"
            "  4. Исправь только проблемные места.\n"
            "  5. Выведи финальный ответ.\n\n"
            "Формат ответа:\n"
            "[ERRORS] (список ошибок, или «нет ошибок»)\n"
            "[FINAL] (итоговый ответ пользователю)\n\n"
            f"Запрос пользователя: {user_text}\n\n"
            f"{drafts_block}"
        )
        for verifier_name, verify_fn in verifiers:
            raw_answer = verify_fn(
                context + "\n\nРоль: Verifier. Только проверка и сборка финала на базе черновиков.",
                verifier_prompt,
            )
            if raw_answer and raw_answer.strip():
                # Извлекаем финальную часть, если Verifier следовал формату
                final_answer = raw_answer.strip()
                if "[FINAL]" in final_answer:
                    final_answer = final_answer.split("[FINAL]", 1)[1].strip()

                self._post_verifier_feedback(user_text, drafts, final_answer, verifier_name)
                used = "+".join(name for name, _ in drafts)
                return final_answer, f"SpecConsensus:{used}→{verifier_name}"

        merged = drafts[0][1]
        return merged, f"SpecConsensus:DraftFallback({drafts[0][0]})"

    # ═══════════════════════════════════════════════════════
    # ОСНОВНАЯ ЛОГИКА
    # ═══════════════════════════════════════════════════════
    def process_logic(self, user_text: str, admin, flasher) -> dict:
        self._runtime_admin = admin
        self._runtime_flasher = flasher
        q_data = self.quantum.generate_state()
        if self.context:
            self.context.set_quantum_state(q_data["name"])
        if self.curiosity:
            self.curiosity.touch_activity(user_text)
        t = user_text.lower()

        # Проверяем напоминания
        if self.memory:
            for r in self.memory.check_reminders():
                self.say(r)

        # Tool Calling — модель сама выбирает инструменты по JSON-схемам
        if self.tool_calling:
            tool_answer = self.tool_calling.try_handle(user_text, admin, flasher)
            if tool_answer:
                self.context.add("user", user_text)
                self.context.add("argos", tool_answer)
                self._remember_dialog_turn(user_text, tool_answer, "ToolCalling")
                if self.db:
                    self.db.log_chat("user", user_text)
                    self.db.log_chat("argos", tool_answer, "ToolCalling")
                self.say(tool_answer)
                return {"answer": tool_answer, "state": "ToolCalling"}

        # Агентный режим — цепочка задач
        agent_result = self.agent.execute_plan(user_text, admin, flasher)
        if agent_result:
            self.context.add("user", user_text)
            self.context.add("argos", agent_result)
            self._remember_dialog_turn(user_text, agent_result, "Agent")
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
            self._remember_dialog_turn(user_text, intent, "System")
            if self.db:
                self.db.log_chat("user", user_text)
                self.db.log_chat("argos", intent, "System")
            self.say(intent)
            return {"answer": intent, "state": "System"}

        # Плагины SkillLoader v2
        if self.skill_loader:
            skill_answer = self.skill_loader.dispatch(user_text, core=self)
            if skill_answer:
                self.context.add("user", user_text)
                self.context.add("argos", skill_answer)
                self._remember_dialog_turn(user_text, skill_answer, "Skill")
                if self.db:
                    self.db.log_chat("user", user_text)
                    self.db.log_chat("argos", skill_answer, "Skill")
                self.say(skill_answer)
                return {"answer": skill_answer, "state": "Skill"}

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
            rag_ctx = self.memory.get_rag_context(user_text, top_k=4)
            if rag_ctx:
                context += f"\n\n{rag_ctx}"

        answer = None
        engine = q_data['name']

        if self.ai_mode == "gemini":
            answer = self._ask_gemini(context, user_text)
            engine = f"{q_data['name']} (Gemini)"
        elif self.ai_mode == "gigachat":
            answer = self._ask_gigachat(context, user_text)
            engine = f"{q_data['name']} (GigaChat)"
        elif self.ai_mode == "yandexgpt":
            answer = self._ask_yandexgpt(context, user_text)
            engine = f"{q_data['name']} (YandexGPT)"
        elif self.ai_mode == "lmstudio":
            answer = self._ask_lmstudio(context, user_text)
            engine = f"{q_data['name']} (LM Studio)"
        elif self.ai_mode == "ollama":
            answer = self._ask_ollama(context, user_text)
            engine = f"{q_data['name']} (Ollama)"
        elif self.ai_mode == "watsonx":
            answer = self._ask_watsonx(context, user_text)
            engine = f"{q_data['name']} (Watsonx)"
        else:
            answer = self._ask_consensus(context, user_text)
            engine = f"{q_data['name']} (Auto-Consensus)"

        if not answer:
            if self.ai_mode == "gemini":
                if self._last_gemini_rate_limited:
                    answer = self._gemini_rate_limit_text()
                else:
                    answer = "Gemini недоступен в текущем режиме. Переключите режим ИИ на Auto, GigaChat, YandexGPT, LM Studio, Watsonx или Ollama."
            elif self.ai_mode == "gigachat":
                answer = "GigaChat недоступен в текущем режиме. Проверьте токен/credentials или переключите режим ИИ."
            elif self.ai_mode == "yandexgpt":
                answer = "YandexGPT недоступен в текущем режиме. Проверьте IAM_TOKEN/FOLDER_ID или переключите режим ИИ."
            elif self.ai_mode == "lmstudio":
                answer = "LM Studio недоступен в текущем режиме. Проверьте LMSTUDIO_BASE_URL/LMSTUDIO_MODEL или переключите режим ИИ."
            elif self.ai_mode == "ollama":
                answer = "Ollama недоступен в текущем режиме. Проверьте локальный сервер Ollama или переключите режим ИИ."
            elif self.ai_mode == "watsonx":
                answer = "Watsonx недоступен. Проверьте WATSONX_API_KEY/WATSONX_PROJECT_ID или переключите режим ИИ."
            else:
                answer = "Связь с ядрами ИИ разорвана. Режим оффлайн."
            engine = "Offline"

        # Сохраняем в контекст и БД
        self.context.add("user", user_text)
        self.context.add("argos", answer)
        self._remember_dialog_turn(user_text, answer, engine)
        if self.db:
            self.db.log_chat("user", user_text)
            self.db.log_chat("argos", answer, engine)

        self.say(answer)
        return {"answer": answer, "state": engine}

    async def process_logic_async(self, user_text: str, admin, flasher) -> dict:
        """Неблокирующий async-вход для UI/ботов.
        Вся синхронная логика выполняется в thread executor.
        """
        return await asyncio.to_thread(self.process_logic, user_text, admin, flasher)

    # ═══════════════════════════════════════════════════════
    # ДИСПЕТЧЕР КОМАНД — 50+ интентов
    # ═══════════════════════════════════════════════════════
    def execute_intent(self, text: str, admin, flasher) -> str | None:
        t = text.lower()

        if self._homeostasis_block_heavy and any(k in t for k in [
            "посмотри на экран", "что на экране", "посмотри в камеру", "анализ фото",
            "проанализируй изображение", "компиля", "compile", "создай прошивку", "прошей шлюз", "прошей gateway"
        ]):
            return "🔥 Гомеостаз: тяжёлая операция временно заблокирована (режим Protective/Unstable)."

        if self.homeostasis and any(k in t for k in ["гомеостаз статус", "статус гомеостаза", "homeostasis status"]):
            return self.homeostasis.status()
        if self.homeostasis and any(k in t for k in ["гомеостаз вкл", "включи гомеостаз", "homeostasis on"]):
            return self.homeostasis.start()
        if self.homeostasis and any(k in t for k in ["гомеостаз выкл", "выключи гомеостаз", "homeostasis off"]):
            return self.homeostasis.stop()

        if self.curiosity and any(k in t for k in ["любопытство статус", "статус любопытства", "curiosity status"]):
            return self.curiosity.status()
        if self.curiosity and any(k in t for k in ["любопытство вкл", "включи любопытство", "curiosity on"]):
            return self.curiosity.start()
        if self.curiosity and any(k in t for k in ["любопытство выкл", "выключи любопытство", "curiosity off"]):
            return self.curiosity.stop()
        if self.curiosity and any(k in t for k in ["любопытство сейчас", "curiosity now"]):
            return self.curiosity.ask_now()

        if self.task_queue and any(k in t for k in ["очередь статус", "queue status"]):
            return self.task_queue.status()
        if self.task_queue and any(k in t for k in ["очередь результаты", "queue results"]):
            return self.task_queue.last_results()
        if any(k in t for k in ["очередь метрики", "queue metrics"]):
            try:
                from src.observability import Metrics
                return Metrics.report()
            except Exception as e:
                return f"❌ Метрики недоступны: {e}"
        if self.task_queue and (t.startswith("в очередь ") or t.startswith("queue run ")):
            cmd = text
            if t.startswith("в очередь "):
                cmd = text[len("в очередь "):].strip()
            elif t.startswith("queue run "):
                cmd = text[len("queue run "):].strip()
            if not cmd:
                return "Формат: в очередь [команда]"
            parts = cmd.split()
            priority = 1 if any(k in cmd.lower() for k in ["срочно", "critical", "urgent"]) else 5
            retries = self.task_queue.default_retries
            deadline = self.task_queue.default_deadline_sec
            backoff_ms = self.task_queue.default_backoff_ms
            task_class = ""
            clean_parts = []
            for item in parts:
                lower = item.lower()
                if lower.startswith("priority="):
                    try:
                        priority = int(lower.split("=", 1)[1])
                    except Exception:
                        pass
                    continue
                if lower.startswith("retries="):
                    try:
                        retries = int(lower.split("=", 1)[1])
                    except Exception:
                        pass
                    continue
                if lower.startswith("deadline="):
                    try:
                        deadline = int(lower.split("=", 1)[1])
                    except Exception:
                        pass
                    continue
                if lower.startswith("backoff="):
                    try:
                        backoff_ms = int(lower.split("=", 1)[1])
                    except Exception:
                        pass
                    continue
                if lower.startswith("class="):
                    try:
                        task_class = lower.split("=", 1)[1].strip().lower()
                    except Exception:
                        task_class = ""
                    continue
                clean_parts.append(item)
            normalized_cmd = " ".join(clean_parts).strip()
            if not normalized_cmd:
                return "Формат: в очередь [команда] [class=system|iot|ai|heavy priority=1..10 retries=N deadline=sec backoff=ms]"
            if not task_class:
                task_class = self._classify_queue_command(normalized_cmd)
            task_id = self.task_queue.submit_ex(
                "logic.command",
                {"command": normalized_cmd},
                priority=priority,
                task_class=task_class,
                max_retries=retries,
                deadline_sec=deadline,
                backoff_ms=backoff_ms,
            )
            return (
                f"📥 Команда поставлена в очередь: #{task_id} "
                f"(class={task_class}, priority={priority}, retries={retries}, deadline={deadline}s, backoff={backoff_ms}ms)"
            )
        if self.task_queue and (t.startswith("очередь воркеры ") or t.startswith("queue workers ")):
            try:
                count = int(text.split()[-1])
                return self.task_queue.set_workers(count)
            except Exception:
                return "Формат: очередь воркеры [число]"

        if any(k in t for k in ["lmstudio статус", "lm studio статус", "lmstudio status", "lm studio status"]):
            return self._lmstudio_status()

        if self.git_ops and any(k in t for k in ["git статус", "гит статус", "git status"]):
            return self.git_ops.status()
        if self.git_ops and any(k in t for k in ["git пуш", "гит пуш", "git push"]):
            return self.git_ops.push()
        if self.git_ops and any(k in t for k in ["git автокоммит и пуш", "гит автокоммит и пуш", "git auto push", "git commit and push"]):
            msg = text
            for marker in ["git автокоммит и пуш", "гит автокоммит и пуш", "git auto push", "git commit and push"]:
                if marker in msg.lower():
                    idx = msg.lower().find(marker)
                    msg = msg[idx + len(marker):].strip()
                    break
            if not msg:
                msg = "chore: argos autonomous update"
            return self.git_ops.commit_and_push(msg)
        if self.git_ops and (t.startswith("git коммит ") or t.startswith("гит коммит ") or t.startswith("git commit ")):
            msg = text
            for marker in ["git коммит", "гит коммит", "git commit"]:
                if marker in msg.lower():
                    idx = msg.lower().find(marker)
                    msg = msg[idx + len(marker):].strip()
                    break
            return self.git_ops.commit(msg)

        if hasattr(admin, "set_alert_callback"):
            admin.set_alert_callback(self._on_alert)

        if hasattr(admin, "set_role") and any(k in t for k in ["роль доступа", "установи роль", "режим доступа"]):
            if "статус" in t and hasattr(admin, "security_status"):
                return admin.security_status()
            role = text.split()[-1].strip().lower()
            return admin.set_role(role)

        if hasattr(admin, "security_status") and any(k in t for k in ["статус безопасности", "security status", "audit status"]):
            return admin.security_status()

        if any(k in t for k in ["оператор режим вкл", "включи операторский режим"]):
            self.operator_mode = True
            return "🎛️ Операторский режим включён. Доступны сценарии: оператор инцидент / оператор диагностика / оператор восстановление"
        if any(k in t for k in ["оператор режим выкл", "выключи операторский режим"]):
            self.operator_mode = False
            return "🎛️ Операторский режим выключен."
        if any(k in t for k in ["оператор инцидент", "сценарий инцидент"]):
            return self._operator_incident(admin)
        if any(k in t for k in ["оператор диагностика", "сценарий диагностика"]):
            return self._operator_diagnostics(admin)
        if any(k in t for k in ["оператор восстановление", "сценарий восстановление"]):
            return self._operator_recovery()

        if self.module_loader and any(k in t for k in ["модули", "список модулей", "modules"]):
            return self.module_loader.list_modules()

        if self.tool_calling and any(k in t for k in ["схемы инструментов", "tool schema", "tool calling schema", "json схемы инструментов"]):
            return json.dumps(self.tool_calling.tool_schemas(), ensure_ascii=False, indent=2)

        # ── Мастер создания умной системы (пошаговый) ─────
        if self._smart_create_wizard is not None:
            if any(k in t.strip() for k in ["отмена", "cancel", "стоп"]):
                self._smart_create_wizard = None
                return "🛑 Мастер создания отменён."
            return self._continue_smart_create_wizard(text)

        # ── Dynamic modules dispatcher ────────────────────
        if self.module_loader:
            mod_answer = self.module_loader.dispatch(text, admin=admin, flasher=flasher)
            if mod_answer:
                return mod_answer

        # ── Home Assistant ────────────────────────────────
        if self.ha:
            if any(k in t for k in ["ha статус", "home assistant статус", "статус home assistant"]):
                return self.ha.health()
            if any(k in t for k in ["ha состояния", "home assistant состояния"]):
                return self.ha.list_states()
            if t.startswith("ha сервис "):
                # ha сервис light turn_on entity_id=light.kitchen brightness=180
                parts = text.split()
                if len(parts) < 4:
                    return "Формат: ha сервис [domain] [service] [key=value ...]"
                domain = parts[2]
                service = parts[3]
                data = {}
                for item in parts[4:]:
                    if "=" in item:
                        key, val = item.split("=", 1)
                        data[key] = val
                return self.ha.call_service(domain, service, data)
            if t.startswith("ha mqtt "):
                # ha mqtt home/livingroom/light/set state=ON brightness=180
                parts = text.split()
                if len(parts) < 3:
                    return "Формат: ha mqtt [topic] [key=value ...]"
                topic = parts[2]
                payload = {}
                for item in parts[3:]:
                    if "=" in item:
                        key, val = item.split("=", 1)
                        payload[key] = val
                if not payload:
                    payload = {"msg": "on"}
                return self.ha.publish_mqtt(topic, payload)

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
            if not self.context.allow_root:
                return "⛔ Команды терминала ограничены текущим квантовым профилем (без root-допуска)."
            cmd = text.split("консоль",1)[-1].strip() if "консоль" in t else text.split("терминал",1)[-1].strip()
            return admin.run_cmd(cmd, user="argos")

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
        if any(k in t for k in ["найди usb чипы", "usb чипы", "смарт прошивка usb", "smart flasher usb"]):
            if hasattr(flasher, "detect_usb_chips_report"):
                return flasher.detect_usb_chips_report()
            return "❌ Smart Flasher недоступен в текущем flasher-модуле."
        if any(k in t for k in ["умная прошивка", "smart flash", "смарт прошивка"]):
            if hasattr(flasher, "smart_flash"):
                parts = text.split()
                port = None
                for p in parts:
                    if p.startswith("/dev/") or p.upper().startswith("COM"):
                        port = p
                        break
                return flasher.smart_flash(port=port)
            return "❌ Smart Flasher недоступен в текущем flasher-модуле."

        # ── Голос ─────────────────────────────────────────
        if any(k in t for k in ["голос вкл", "включи голос"]):
            self.voice_on = True; return "🔊 Голосовой модуль активирован."
        if any(k in t for k in ["голос выкл", "выключи голос"]):
            self.voice_on = False; return "🔇 Голосовой модуль отключён."
        if any(k in t for k in ["режим ии авто", "модель авто", "ai mode auto"]):
            return self.set_ai_mode("auto")
        if any(k in t for k in ["режим ии gemini", "модель gemini", "ai mode gemini"]):
            return self.set_ai_mode("gemini")
        if any(k in t for k in ["режим ии gigachat", "модель gigachat", "ai mode gigachat", "режим ии гигачат"]):
            return self.set_ai_mode("gigachat")
        if any(k in t for k in ["режим ии yandexgpt", "модель yandexgpt", "ai mode yandexgpt", "режим ии яндекс"]):
            return self.set_ai_mode("yandexgpt")
        if any(k in t for k in ["режим ии lmstudio", "модель lmstudio", "ai mode lmstudio", "режим ии lm studio", "модель lm studio"]):
            return self.set_ai_mode("lmstudio")
        if any(k in t for k in ["режим ии ollama", "модель ollama", "ai mode ollama"]):
            return self.set_ai_mode("ollama")
        if any(k in t for k in ["текущий режим ии", "какая модель", "ai mode"]):
            return f"🤖 Текущий режим ИИ: {self.ai_mode_label()}"
        if any(k in t for k in ["включи wake word", "wake word вкл"]):
            return self.start_wake_word(admin, flasher)

        # ── Навыки ────────────────────────────────────────
        if self.skill_loader and any(k in t for k in ["навыки v2", "skills v2", "skillloader"]):
            return self.skill_loader.list_skills()
        if self.skill_loader and t.startswith("загрузи навык "):
            name = text.split("загрузи навык ", 1)[-1].strip()
            return self.skill_loader.load(name, core=self)
        if self.skill_loader and t.startswith("выгрузи навык "):
            name = text.split("выгрузи навык ", 1)[-1].strip()
            return self.skill_loader.unload(name)
        if self.skill_loader and t.startswith("перезагрузи навык "):
            name = text.split("перезагрузи навык ", 1)[-1].strip()
            return self.skill_loader.reload(name, core=self)

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
            if self.skill_loader:
                return self.skill_loader.list_skills()
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
            if any(k in t for k in ["поиск по памяти", "найди в памяти", "rag память"]):
                q = text
                for pref in ["поиск по памяти", "найди в памяти", "rag память", "аргос"]:
                    q = q.replace(pref, "")
                q = q.strip()
                if not q:
                    return "Формат: найди в памяти [запрос]"
                rag = self.memory.get_rag_context(q, top_k=5)
                return rag or "Ничего релевантного в векторной памяти не найдено."
            if any(k in t for k in ["граф знаний", "связи памяти", "мои связи"]):
                return self.memory.graph_report()
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
            if any(k in t for k in ["каждые", "напомни", "ежедневно"]) or "через" in t or (t.strip().startswith("в ") and ":" in t):
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
        if "ARGOS-BOOT-CONFIRM" in t.upper():
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
        if any(k in t for k in ["p2p телеметрия", "телеметрия p2p", "p2p telemetry"]):
            return self.p2p.network_telemetry() if self.p2p else "P2P не запущен. Команда: запусти p2p"
        if any(k in t for k in ["p2p tuning", "p2p тюнинг", "p2p веса", "p2p веса"]):
            return self.p2p.routing_tuning_report() if self.p2p else "P2P не запущен. Команда: запусти p2p"
        if t.startswith("p2p вес "):
            if not self.p2p:
                return "P2P не запущен. Команда: запусти p2p"
            parts = text.split()
            if len(parts) < 4:
                return "Формат: p2p вес [name] [value]"
            return self.p2p.set_routing_weight(parts[2], parts[3])
        if t.startswith("p2p failover"):
            if not self.p2p:
                return "P2P не запущен. Команда: запусти p2p"
            parts = text.split()
            if len(parts) < 3:
                return "Формат: p2p failover [1..5]"
            return self.p2p.set_failover_limit(parts[2])
        if any(k in t for k in ["протокол p2p", "p2p протокол", "libp2p", "zkp"]):
            return p2p_protocol_roadmap()
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
                route_type = "heavy" if any(k in q.lower() for k in ["vision", "камер", "компиля", "compile", "прошив"]) else None
                return self.p2p.route_query(q or "Статус сети Аргоса.", task_type=route_type)
            return "P2P не запущен."

        # ── DAG ───────────────────────────────────────────
        if self.dag_manager and any(k in t for k in ["список dag", "dag список", "доступные dag"]):
            return self.dag_manager.list_dags()
        if self.dag_manager and ("запусти_dag" in t or "запусти dag" in t):
            name = text.replace("запусти_dag", "").replace("запусти dag", "").strip()
            name = name.replace(".json", "")
            name = name.split("/")[-1]
            if not name:
                return "Формат: запусти_dag имя_графа"
            return self.dag_manager.run(name)
        if self.dag_manager and ("создай_dag" in t or "создай dag" in t):
            desc = text.replace("создай_dag", "").replace("создай dag", "").strip()
            if not desc:
                return "Формат: создай_dag описание шагов"
            return self.dag_manager.create_from_text(desc)
        if self.dag_manager and any(k in t for k in ["синхронизируй dag", "dag sync"]):
            return self.dag_manager.sync_to_p2p()

        # ── GitHub Marketplace ────────────────────────────
        if self.marketplace and "установи навык из github" in t:
            spec = text.split("установи навык из github", 1)[-1].strip().split()
            if len(spec) < 2:
                return "Формат: установи навык из github USER/REPO SKILL"
            return self.marketplace.install(repo=spec[0], skill_name=spec[1])
        if self.marketplace and "обнови из github" in t:
            spec = text.split("обнови из github", 1)[-1].strip().split()
            if len(spec) < 2:
                return "Формат: обнови из github USER/REPO SKILL"
            return self.marketplace.update(repo=spec[0], skill_name=spec[1])
        if self.marketplace and "оцени навык" in t:
            spec = text.split("оцени навык", 1)[-1].strip().split()
            if len(spec) < 2:
                return "Формат: оцени навык SKILL [1-5]"
            return self.marketplace.rate(spec[0], spec[1])
        if self.marketplace and any(k in t for k in ["рейтинг навыков", "оценки навыков"]):
            return self.marketplace.ratings_report()

        # ── История ───────────────────────────────────────
        if any(k in t for k in ["история", "предыдущие разговоры"]):
            return self.db.format_history(10) if self.db else "БД не подключена."

        # ══════════════════════════════════════════════════
        # УМНЫЕ СИСТЕМЫ (дом, теплица, гараж, погреб, инкубатор, аквариум, террариум)
        # ══════════════════════════════════════════════════
        if self.smart_sys:
            if any(k in t for k in ["создай умную систему", "добавь умную систему", "мастер умной системы"]):
                return self._start_smart_create_wizard()
            if any(k in t for k in ["умные системы", "статус систем", "мои системы", "умный дом"]):
                return self.smart_sys.full_status()
            if any(k in t for k in ["типы систем", "доступные системы"]):
                return self.smart_sys.available_types()
            if "добавь систему" in t or "создай систему" in t:
                parts = text.replace("добавь систему","").replace("создай систему","").strip().split()
                if not parts:
                    return self.smart_sys.available_types()
                sys_type = parts[0]
                sys_id   = parts[1] if len(parts) > 1 else None
                return self.smart_sys.add_system(sys_type, sys_id)
            if "обнови сенсор" in t or "сенсор" in t and "=" in t:
                # Формат: обнови сенсор [система] [сенсор] [значение]
                parts = text.replace("обнови сенсор","").strip().split()
                if len(parts) >= 3:
                    return self.smart_sys.update(parts[0], parts[1], parts[2])
                return "Формат: обнови сенсор [id_системы] [сенсор] [значение]"
            if any(k in t for k in ["включи", "выключи", "установи"]) and self.smart_sys.systems:
                # включи полив greenhouse / выключи обогрев home
                for action_w, state in [("включи","on"),("выключи","off"),("установи","set")]:
                    if action_w in t:
                        rest = text.split(action_w, 1)[-1].strip().split()
                        if len(rest) >= 2:
                            actuator = rest[0]
                            sys_id   = rest[1]
                            if sys_id in self.smart_sys.systems:
                                return self.smart_sys.command(sys_id, actuator, state)
                        break
            if "добавь правило" in t:
                # добавь правило [система] если [условие] то [действие]
                rest = text.split("добавь правило", 1)[-1].strip()
                parts = rest.split(maxsplit=1)
                if len(parts) >= 2 and parts[0] in self.smart_sys.systems:
                    rule_text = parts[1]
                    if "если" in rule_text and "то" in rule_text:
                        cond = rule_text.split("если")[1].split("то")[0].strip()
                        act  = rule_text.split("то")[1].strip()
                        return self.smart_sys.systems[parts[0]].add_rule(cond, act)
                return "Формат: добавь правило [система] если [условие] то [действие]"

        # ══════════════════════════════════════════════════
        # IoT МОСТ (устройства, протоколы)
        # ══════════════════════════════════════════════════
        if self.iot_bridge:
            if any(k in t for k in ["iot статус", "iot устройства", "устройства iot"]):
                return self.iot_bridge.status()
            if any(k in t for k in ["iot возможности", "iot capability", "iot матрица", "возможности iot"]):
                return self.iot_bridge.get_capabilities()
            if any(k in t for k in ["iot протоколы", "протоколы iot", "пром протоколы", "какие протоколы"]):
                return self._iot_protocols_help()
            if "зарегистрируй устройство" in t or "добавь устройство" in t:
                # добавь устройство [id] [тип] [протокол] [адрес] [имя]
                parts = text.split("устройство", 1)[-1].strip().split()
                if len(parts) >= 3:
                    dev_id, dtype, proto = parts[0], parts[1], parts[2]
                    addr = parts[3] if len(parts) > 3 else ""
                    name = parts[4] if len(parts) > 4 else dev_id
                    return self.iot_bridge.register_device(dev_id, dtype, proto, addr, name)
                return "Формат: добавь устройство [id] [тип] [протокол] [адрес] [имя]"
            if "статус устройства" in t or "мониторинг устройства" in t:
                parts = text.split("устройства" if "устройства" in t else "устройство")[-1].strip().split()
                if parts:
                    return self.iot_bridge.device_status(parts[0])
                return "Формат: статус устройства [id]"
            if "подключи zigbee" in t:
                parts = text.split("подключи zigbee")[-1].strip().split()
                host = parts[0] if parts else "localhost"
                port = int(parts[1]) if len(parts) > 1 else 1883
                return self.iot_bridge.connect_zigbee(host, port)
            if "подключи lora" in t:
                parts = text.split("подключи lora")[-1].strip().split()
                port = parts[0] if parts else "/dev/ttyUSB0"
                baud = int(parts[1]) if len(parts) > 1 else 9600
                return self.iot_bridge.connect_lora(port, baud)
            if "запусти mesh" in t or "mesh старт" in t:
                return self.iot_bridge.start_mesh()
            if "подключи mqtt" in t:
                parts = text.split("подключи mqtt")[-1].strip().split()
                host = parts[0] if parts else "localhost"
                port = int(parts[1]) if len(parts) > 1 else 1883
                return self.iot_bridge.connect_mqtt(host, port)
            if "подключи modbus tcp" in t:
                parts = text.split("tcp")[-1].strip().split()
                host = parts[0] if parts else "127.0.0.1"
                port = int(parts[1]) if len(parts) > 1 else 502
                return self.iot_bridge.modbus.connect_tcp(host, port)
            if "подключи modbus" in t and "tcp" not in t:
                parts = text.split("подключи modbus")[-1].strip().split()
                port = parts[0] if parts else "/dev/ttyUSB0"
                baud = int(parts[1]) if len(parts) > 1 else 9600
                return self.iot_bridge.modbus.connect_rtu(port, baud)
            if "modbus чтение" in t or "modbus read" in t:
                # Формат: modbus чтение [address] [count] [slave]
                parts = text.split("чтение")[-1].strip().split()
                if len(parts) >= 3:
                    try:
                        return self.iot_bridge.modbus.read_holding(int(parts[0]), int(parts[1]), int(parts[2]))
                    except Exception:
                        return "Формат: modbus чтение [адрес] [количество] [unit_id]"
                return "Формат: modbus чтение [адрес] [количество] [unit_id]"
            if "modbus запись" in t or "modbus write" in t:
                # Формат: modbus запись [address] [value] [slave]
                parts = text.split("запись")[-1].strip().split()
                if len(parts) >= 3:
                    try:
                        return self.iot_bridge.modbus.write_holding(int(parts[0]), int(parts[1]), int(parts[2]))
                    except Exception:
                        return "Формат: modbus запись [адрес] [значение] [unit_id]"
                return "Формат: modbus запись [адрес] [значение] [unit_id]"
            if any(k in t for k in ["команда устройству", "отправь команду"]):
                parts = text.split("устройству" if "устройству" in t else "команду")[-1].strip().split()
                if len(parts) >= 2:
                    return self.iot_bridge.send_command(parts[0], parts[1],
                                                       parts[2] if len(parts) > 2 else None)
                return "Формат: команда устройству [id] [команда] [значение]"

        # ══════════════════════════════════════════════════
        # MESH-СЕТЬ (Zigbee, LoRa, WiFi Mesh)
        # ══════════════════════════════════════════════════
        if self.mesh_net:
            if any(k in t for k in ["статус mesh", "mesh статус", "mesh сеть", "mesh-сеть"]):
                return self.mesh_net.status_report()
            if "запусти zigbee" in t:
                parts = text.split("запусти zigbee")[-1].strip().split()
                port = parts[0] if parts else "/dev/ttyUSB0"
                baud = int(parts[1]) if len(parts) > 1 else 115200
                return self.mesh_net.start_zigbee(port, baud)
            if "запусти lora" in t:
                parts = text.split("запусти lora")[-1].strip().split()
                port = parts[0] if parts else "/dev/ttyUSB1"
                baud = int(parts[1]) if len(parts) > 1 else 9600
                return self.mesh_net.start_lora(port, baud)
            if "запусти wifi mesh" in t:
                ssid = text.split("запусти wifi mesh")[-1].strip() or "ArgosNet"
                return self.mesh_net.start_wifi_mesh(ssid)
            if "добавь mesh устройство" in t:
                parts = text.split("mesh устройство")[-1].strip().split()
                if len(parts) >= 3:
                    return self.mesh_net.add_device(parts[0], parts[1], parts[2],
                                                    parts[3] if len(parts) > 3 else "",
                                                    parts[4] if len(parts) > 4 else "")
                return "Формат: добавь mesh устройство [id] [протокол] [адрес] [имя] [комната]"
            if "mesh broadcast" in t or "mesh рассылка" in t:
                parts = text.split("broadcast" if "broadcast" in t else "рассылка")[-1].strip().split(maxsplit=1)
                if len(parts) >= 2:
                    return self.mesh_net.broadcast(parts[0], parts[1])
                return "Формат: mesh broadcast [протокол] [команда]"
            if "прошей gateway" in t:
                parts = text.split("gateway")[-1].strip().split()
                if len(parts) >= 1:
                    port = parts[0]
                    fw   = parts[1] if len(parts) > 1 else "zigbee_gateway"
                    return self.mesh_net.flash_gateway(port, fw)
                return "Формат: прошей gateway [порт] [прошивка]"

        # ══════════════════════════════════════════════════
        # IoT ШЛЮЗЫ (создание, конфиг, прошивка)
        # ══════════════════════════════════════════════════
        if self.gateway_mgr:
            if any(k in t for k in ["список шлюзов", "шлюзы", "gateways"]):
                return self.gateway_mgr.list_gateways()
            if any(k in t for k in ["шаблоны шлюзов", "типы шлюзов"]):
                return self.gateway_mgr.list_templates()
            if any(k in t for k in ["изучи протокол", "выучи протокол", "научи протокол"]):
                tail = text
                for marker in ("изучи протокол", "выучи протокол", "научи протокол"):
                    if marker in t:
                        tail = text.split(marker, 1)[-1].strip()
                        break
                parts = tail.split()
                if len(parts) >= 2:
                    template = parts[0]
                    protocol = parts[1]
                    firmware = parts[2] if len(parts) > 2 else ""
                    description = " ".join(parts[3:]) if len(parts) > 3 else f"Автошаблон для {protocol}"
                    return self.gateway_mgr.register_template(
                        name=template,
                        description=description,
                        protocol=protocol,
                        firmware=firmware,
                    )
                return ("Формат: изучи протокол [шаблон] [протокол] [прошивка?] [описание?]\n"
                        "Пример: изучи протокол bt_gateway bluetooth custom_bridge BLE шлюз")
            if any(k in t for k in ["изучи устройство", "выучи устройство", "изучи устроц", "выучи устроц"]):
                tail = text
                for marker in ("изучи устройство", "выучи устройство", "изучи устроц", "выучи устроц"):
                    if marker in t:
                        tail = text.split(marker, 1)[-1].strip()
                        break
                parts = tail.split()
                if len(parts) >= 2:
                    template = parts[0]
                    protocol = parts[1]
                    hardware = " ".join(parts[2:]) if len(parts) > 2 else "Generic gateway"
                    return self.gateway_mgr.register_template(
                        name=template,
                        description=f"Шаблон устройства: {hardware}",
                        protocol=protocol,
                        hardware=hardware,
                    )
                return ("Формат: изучи устройство [шаблон] [протокол] [hardware?]\n"
                        "Пример: изучи устройство rtu_bridge modbus USB-RS485 адаптер")
            if "создай прошивку" in t or "собери прошивку" in t:
                # создай прошивку [id] [шаблон] [порт?]
                tail = text.split("прошивку", 1)[-1].strip().split()
                if len(tail) >= 2:
                    gw_id = tail[0]
                    template = tail[1]
                    port = tail[2] if len(tail) > 2 else None
                    return self.gateway_mgr.prepare_firmware(gw_id, template, port)
                return f"Формат: создай прошивку [id] [шаблон] [порт]\n{self.gateway_mgr.list_templates()}"
            if "создай шлюз" in t or "создай gateway" in t:
                parts = text.split("шлюз" if "шлюз" in t else "gateway")[-1].strip().split()
                if len(parts) >= 2:
                    return self.gateway_mgr.create_gateway(parts[0], parts[1])
                return f"Формат: создай шлюз [id] [шаблон]\n{self.gateway_mgr.list_templates()}"
            if "прошей шлюз" in t or "flash gateway" in t:
                parts = text.split("шлюз" if "шлюз" in t else "gateway")[-1].strip().split()
                if parts:
                    port = parts[1] if len(parts) > 1 else None
                    return self.gateway_mgr.flash_gateway(parts[0], port)
                return "Формат: прошей шлюз [id] [порт]"
            if any(k in t for k in ["здоровье шлюзов", "health шлюзов", "проверь шлюзы"]):
                parts = text.split()
                gw_id = parts[-1] if len(parts) >= 3 and parts[-1] not in {"шлюзов", "шлюзы"} else None
                return self.gateway_mgr.health_check(gw_id)
            if "откат прошивки" in t:
                parts = text.split("откат прошивки", 1)[-1].strip().split()
                if not parts:
                    return "Формат: откат прошивки [id] [шагов?]"
                steps = 1
                if len(parts) > 1:
                    try:
                        steps = max(1, int(parts[1]))
                    except Exception:
                        steps = 1
                return self.gateway_mgr.rollback_firmware(parts[0], steps)
            if "конфиг шлюза" in t:
                gw_id = text.split("конфиг шлюза")[-1].strip().split()[0] if text.split("конфиг шлюза")[-1].strip() else ""
                if gw_id:
                    return self.gateway_mgr.get_config(gw_id)
                return "Формат: конфиг шлюза [id]"

        # ══════════════════════════════════════════════════
        # NFC МЕТКИ
        # ══════════════════════════════════════════════════
        if self.nfc:
            if any(k in t for k in ["nfc статус", "статус nfc", "nfc status"]):
                return json.dumps(self.nfc.get_status(), ensure_ascii=False, indent=2)
            if any(k in t for k in ["nfc метки", "список меток", "nfc tags"]):
                tags = self.nfc.list_tags()
                if not tags:
                    return "📡 NFC: Нет зарегистрированных меток."
                lines = ["📡 NFC МЕТКИ:"]
                for tag in tags:
                    lines.append(f"  • {tag.name} (UID: {tag.uid}) — {tag.action} [{tag.location}]")
                return "\n".join(lines)
            if any(k in t for k in ["nfc скан", "nfc сканирование", "сканируй nfc"]):
                result = self.nfc.scan_single(timeout=10)
                if result:
                    return f"📡 NFC: найдена метка — UID: {result.get('uid', '?')}, тип: {result.get('type', '?')}"
                return "📡 NFC: метка не обнаружена (таймаут 10с)"
            if "nfc регистрация" in t or "зарегистрируй метку" in t:
                # nfc регистрация [uid] [имя] [действие] [данные]
                tail = text.split("регистрация" if "регистрация" in t else "метку", 1)[-1].strip().split()
                if len(tail) >= 3:
                    from src.connectivity.nfc_manager import TagAction
                    uid, name = tail[0], tail[1]
                    action_str = tail[2] if len(tail) > 2 else "log_event"
                    action = TagAction.LOG_EVENT
                    for a in TagAction:
                        if a.value == action_str:
                            action = a
                            break
                    data = {"payload": " ".join(tail[3:])} if len(tail) > 3 else {}
                    tag = self.nfc.register_tag(uid, name, action, data)
                    return f"📡 NFC: метка '{tag.name}' зарегистрирована (UID: {tag.uid})"
                return "Формат: nfc регистрация [uid] [имя] [действие] [данные...]"
            if "nfc удали" in t or "удали метку" in t:
                tail = text.split("удали", 1)[-1].strip().split()
                if tail:
                    ok = self.nfc.unregister_tag(tail[0])
                    return f"📡 NFC: метка {'удалена' if ok else 'не найдена'}"
                return "Формат: nfc удали [uid]"

        # ══════════════════════════════════════════════════
        # USB ДИАГНОСТИКА
        # ══════════════════════════════════════════════════
        if self.usb_diag:
            if any(k in t for k in ["usb статус", "статус usb", "usb status"]):
                return json.dumps(self.usb_diag.get_status(), ensure_ascii=False, indent=2)
            if any(k in t for k in ["usb скан", "usb устройства", "usb scan", "usb devices"]):
                devices = self.usb_diag.scan_devices()
                if not devices:
                    return "🔌 USB: устройства не обнаружены."
                lines = ["🔌 USB УСТРОЙСТВА:"]
                for d in devices:
                    auth = "✓" if d.get("authorized") else "✗"
                    lines.append(f"  [{auth}] {d.get('port', '?')}: {d.get('description', '?')} "
                                 f"({d.get('vid', '')}:{d.get('pid', '')}) — {d.get('device_type', '?')}")
                return "\n".join(lines)
            if any(k in t for k in ["usb авторизованные", "usb authorized"]):
                devs = self.usb_diag.list_authorized()
                if not devs:
                    return "🔌 USB: нет авторизованных устройств."
                lines = ["🔌 АВТОРИЗОВАННЫЕ USB:"]
                for d in devs:
                    lines.append(f"  • {d.name} ({d.vid}:{d.pid}) — {d.device_type}")
                return "\n".join(lines)

        # ══════════════════════════════════════════════════
        # BLUETOOTH СКАНЕР
        # ══════════════════════════════════════════════════
        if self.bt_scanner:
            if any(k in t for k in ["bt статус", "bluetooth статус", "bt status"]):
                return json.dumps(self.bt_scanner.get_statistics(), ensure_ascii=False, indent=2)
            if any(k in t for k in ["bt инвентарь", "bt devices", "bluetooth устройства", "bt устройства"]):
                inv = self.bt_scanner.get_inventory()
                if not inv:
                    return "📶 BT: инвентарь пуст."
                lines = ["📶 BLUETOOTH ИНВЕНТАРЬ:"]
                for d in inv[:30]:
                    name = d.get("name") or d.get("address", "?")
                    lines.append(f"  • {name} — {d.get('device_type', '?')} (RSSI: {d.get('rssi', '?')})")
                if len(inv) > 30:
                    lines.append(f"  ... и ещё {len(inv) - 30}")
                return "\n".join(lines)
            if any(k in t for k in ["bt скан", "bluetooth скан", "bt scan"]):
                duration = 10.0
                parts = text.split()
                for p in parts:
                    try:
                        duration = float(p)
                        break
                    except ValueError:
                        pass
                devices = self.bt_scanner.scan_sync(duration)
                return f"📶 BT: обнаружено {len(devices)} устройств за {duration}с."
            if any(k in t for k in ["bt iot", "bt iot устройства", "bluetooth iot"]):
                iot = self.bt_scanner.get_iot_devices()
                if not iot:
                    return "📶 BT: IoT-устройства не найдены."
                lines = ["📶 BT IoT УСТРОЙСТВА:"]
                for d in iot:
                    lines.append(f"  • {d.name or d.address} — {d.device_type.value}")
                return "\n".join(lines)

        # ── AWA-Core ──────────────────────────────────────
        if self.awa:
            if any(k in t for k in ["awa статус", "awa status", "координатор статус"]):
                return self.awa.status()
            if any(k in t for k in ["awa модули", "awa modules", "координатор модули"]):
                return self.awa.module_list()
            if any(k in t for k in ["awa история", "awa history", "координатор история"]):
                return self.awa.decision_history()
            if any(k in t for k in ["awa stale", "awa проверка"]):
                stale = self.awa.check_stale()
                if not stale:
                    return "🧠 AWA: все модули отвечают вовремя."
                return "🧠 AWA: устаревшие модули — " + ", ".join(stale)

        # ── Adaptive Drafter ──────────────────────────────
        if self.drafter:
            if any(k in t for k in ["drafter статус", "tlt статус", "drafter status"]):
                return self.drafter.status()
            if any(k in t for k in ["drafter метрики", "tlt метрики", "drafter metrics"]):
                m = self.drafter.get_metrics()
                lines = ["📊 DRAFTER МЕТРИКИ:"]
                for k2, v in m.items():
                    lines.append(f"  {k2}: {v}")
                return "\n".join(lines)
            if any(k in t for k in ["drafter сброс кэша", "tlt сброс", "drafter flush"]):
                return self.drafter.invalidate_cache()

        # ── Self-Healing ──────────────────────────────────
        if self.healer:
            if any(k in t for k in ["healing статус", "самоисцеление статус", "healer status"]):
                return self.healer.status()
            if any(k in t for k in ["healing история", "самоисцеление история", "healer history"]):
                return self.healer.history_json()
            if any(k in t for k in ["healing валидация", "healer validate", "самоисцеление проверка"]):
                return self.healer.validate_all_src()

        # ── AirSnitch ─────────────────────────────────────
        if self.air_snitch:
            if any(k in t for k in ["эфир статус", "airsnitch статус", "sdr статус", "радио статус"]):
                return self.air_snitch.status()
            if any(k in t for k in ["эфир скан", "airsnitch скан", "sdr скан", "скан эфира"]):
                return self.air_snitch.scan_all_bands()
            if any(k in t for k in ["эфир монитор", "airsnitch монитор", "sdr монитор"]):
                return self.air_snitch.start_monitor()
            if any(k in t for k in ["эфир стоп", "airsnitch стоп", "sdr стоп"]):
                return self.air_snitch.stop_monitor()
            if any(k in t for k in ["эфир пакеты", "airsnitch пакеты", "sdr пакеты"]):
                pkts = self.air_snitch.get_packets()
                if not pkts:
                    return "📻 AirSnitch: пакетов не перехвачено."
                lines = ["📻 ПЕРЕХВАЧЕННЫЕ ПАКЕТЫ:"]
                for p in pkts[-20:]:
                    lines.append(f"  [{p.get('freq_mhz', '?')} МГц] {p.get('protocol', '?')} — {p.get('summary', '')}")
                return "\n".join(lines)

        # ── WiFi Sentinel ─────────────────────────────────
        if self.wifi_sentinel:
            if any(k in t for k in ["wifi статус", "wifi sentinel", "wifi status"]):
                return self.wifi_sentinel.status()
            if any(k in t for k in ["wifi скан", "wifi scan", "сканируй wifi"]):
                aps = self.wifi_sentinel.scan_aps()
                if not aps:
                    return "📡 WiFi: точки доступа не обнаружены."
                lines = [f"📡 WiFi: обнаружено {len(aps)} точек доступа:"]
                for ap in aps[:20]:
                    d = ap.to_dict()
                    lines.append(f"  • {d.get('ssid', '?')} ({d.get('bssid', '?')}) ch{d.get('channel', '?')} {d.get('signal_dbm', '?')}dBm — {d.get('encryption', '?')}")
                return "\n".join(lines)
            if any(k in t for k in ["wifi ловушка", "wifi honeypot", "honeypot вкл"]):
                return self.wifi_sentinel.start_honeypot()
            if any(k in t for k in ["wifi ловушка стоп", "honeypot выкл", "honeypot стоп"]):
                return self.wifi_sentinel.stop_honeypot()
            if any(k in t for k in ["wifi монитор", "wifi monitor"]):
                return self.wifi_sentinel.start_monitor()
            if any(k in t for k in ["wifi инциденты", "wifi incidents", "wifi угрозы"]):
                incidents = self.wifi_sentinel.get_incidents()
                if not incidents:
                    return "🛡️ WiFi Sentinel: инцидентов нет."
                lines = ["🛡️ WiFi ИНЦИДЕНТЫ:"]
                for inc in incidents[-15:]:
                    lines.append(f"  [{inc.get('threat_level', '?')}] {inc.get('type', '?')} — {inc.get('description', '')}")
                return "\n".join(lines)

        # ── SmartHome Override ────────────────────────────
        if self.smarthome:
            if any(k in t for k in ["smarthome статус", "override статус", "smarthome status"]):
                return self.smarthome.status()
            if any(k in t for k in ["smarthome устройства", "override устройства", "smarthome devices"]):
                devs = self.smarthome.list_devices()
                if not devs:
                    return "🏠 SmartHome Override: устройств нет."
                lines = ["🏠 OVERRIDE УСТРОЙСТВА:"]
                for d in devs:
                    lines.append(f"  • {d.get('device_id', '?')} — {d.get('friendly_name', '?')} [{d.get('protocol', '?')}] cloud={'blocked' if d.get('cloud_blocked') else 'allowed'}")
                return "\n".join(lines)
            if any(k in t for k in ["smarthome старт", "override старт", "smarthome start"]):
                return self.smarthome.start()
            if t.startswith("smarthome блокируй облако ") or t.startswith("override block "):
                dev_id = t.split()[-1]
                return self.smarthome.block_cloud(dev_id)
            if t.startswith("smarthome команда ") or t.startswith("override cmd "):
                parts = t.split(maxsplit=2)
                if len(parts) >= 3:
                    dev_id = parts[1] if t.startswith("override") else parts[2].split()[0] if len(parts[2].split()) > 0 else ""
                    return f"Используй формат: smarthome команда [device_id] {{json}}"

        # ── Power Sentry ──────────────────────────────────
        if self.power_sentry:
            if any(k in t for k in ["питание статус", "power статус", "ups статус", "power sentry"]):
                return self.power_sentry.status()
            if any(k in t for k in ["питание старт", "power start", "power sentry start"]):
                return self.power_sentry.start()
            if any(k in t for k in ["питание ups", "power ups list", "список ups"]):
                ups_list = self.power_sentry.list_ups()
                if not ups_list:
                    return "🔋 UPS: не обнаружены."
                lines = ["🔋 UPS УСТРОЙСТВА:"]
                for u in ups_list:
                    lines.append(f"  • {u.get('name', '?')} — {u.get('status', '?')} charge={u.get('battery_pct', '?')}% load={u.get('load_pct', '?')}%")
                return "\n".join(lines)
            if any(k in t for k in ["питание показания", "power readings", "показания датчиков питания"]):
                rds = self.power_sentry.get_readings()
                if not rds:
                    return "🔋 Показания: нет данных."
                lines = ["🔋 ПОКАЗАНИЯ ПИТАНИЯ:"]
                for r in rds[-10:]:
                    lines.append(f"  {r.get('sensor_id', '?')}: {r.get('voltage_v', '?')}V {r.get('current_a', '?')}A {r.get('power_w', '?')}W")
                return "\n".join(lines)
            if any(k in t for k in ["аварийное отключение", "power emergency", "emergency arm"]):
                return self.power_sentry.arm_emergency()

        # ── Emergency Purge ───────────────────────────────
        if self.purge:
            if any(k in t for k in ["purge статус", "очистка статус", "purge status"]):
                return self.purge.status()
            if any(k in t for k in ["purge история", "очистка история", "purge history"]):
                return self.purge.history()
            if t.startswith("purge запрос ") or t.startswith("очистка запрос "):
                parts = t.split()
                level = parts[2] if len(parts) > 2 else "logs"
                return self.purge.request_purge(level)
            if t.startswith("purge подтверди ") or t.startswith("очистка подтверди "):
                code = t.split()[-1]
                return self.purge.confirm_purge(code)
            if any(k in t for k in ["purge отмена", "очистка отмена", "purge cancel"]):
                return self.purge.cancel_purge()

        # ── Container Isolation ───────────────────────────
        if self.containers:
            if any(k in t for k in ["контейнер статус", "container статус", "isolation статус", "контейнеры статус"]):
                return self.containers.status()
            if any(k in t for k in ["контейнер список", "container list", "контейнеры"]):
                return self.containers.list_containers()
            if t.startswith("контейнер запуск ") or t.startswith("container launch "):
                parts = t.split()
                module = parts[2] if len(parts) > 2 else ""
                if module:
                    return self.containers.launch(module)
                return "Укажи модуль: контейнер запуск [module_name]"
            if t.startswith("контейнер стоп ") or t.startswith("container stop "):
                name = t.split()[-1]
                return self.containers.stop(name)
            if t.startswith("контейнер логи ") or t.startswith("container logs "):
                name = t.split()[-1]
                return self.containers.logs(name)
            if any(k in t for k in ["контейнер watchdog", "container watchdog"]):
                return self.containers.start_watchdog()
            if any(k in t for k in ["контейнер очистка", "container cleanup"]):
                return self.containers.cleanup()

        # ── Master Auth ───────────────────────────────────
        if self.master_auth:
            if any(k in t for k in ["auth статус", "авторизация статус", "auth status"]):
                return self.master_auth.status()
            if t.startswith("auth ключ ") or t.startswith("auth verify "):
                key = t.split(maxsplit=2)[-1]
                ok = self.master_auth.verify(key)
                return "🔓 Доступ разрешён." if ok else "🔒 Доступ запрещён."
            if any(k in t for k in ["auth разлогин", "auth revoke", "авторизация сброс"]):
                return self.master_auth.revoke()

        # ── Biosphere DAG ─────────────────────────────────
        if self.biosphere_dag:
            if any(k in t for k in ["биосфера статус", "biosphere статус", "biosphere status"]):
                return self.biosphere_dag.status()
            if any(k in t for k in ["биосфера цикл", "biosphere cycle", "биосфера сейчас"]):
                return self.biosphere_dag.run_cycle()
            if any(k in t for k in ["биосфера старт", "biosphere start"]):
                interval = 30.0
                for p in t.split():
                    try:
                        interval = float(p)
                        break
                    except ValueError:
                        pass
                return self.biosphere_dag.start(interval)
            if any(k in t for k in ["биосфера стоп", "biosphere stop"]):
                return self.biosphere_dag.stop()
            if any(k in t for k in ["биосфера результат", "biosphere last"]):
                return self.biosphere_dag.get_last_result()
            if t.startswith("биосфера цель ") or t.startswith("biosphere target "):
                parts = t.split()
                if len(parts) >= 4:
                    key = parts[2]
                    try:
                        val = float(parts[3])
                        return self.biosphere_dag.set_target(key, val)
                    except ValueError:
                        return "Формат: биосфера цель [ключ] [значение]"

        # ── IBM Quantum ───────────────────────────────────
        if any(k in t for k in ["ibm квантовый", "ibm quantum", "квантовый мост"]):
            try:
                return self.quantum.check_ibm_status()
            except Exception as e:
                return f"⚠️ IBM Quantum: {e}"

        # ── Помощь ────────────────────────────────────────
        if t.strip() in ("помощь", "команды", "что умеешь", "help", "?"):
            return self._help()

        return None

    def _operator_incident(self, admin) -> str:
        lines = ["🚨 ОПЕРАТОР: ИНЦИДЕНТ"]
        lines.append(admin.get_stats())
        if self.alerts:
            lines.append(self.alerts.status())
        if self.gateway_mgr:
            lines.append(self.gateway_mgr.health_check())
        lines.append("Рекомендация: запусти 'оператор диагностика' для детального анализа.")
        return "\n\n".join(lines)

    def _operator_diagnostics(self, admin) -> str:
        lines = ["🩺 ОПЕРАТОР: ДИАГНОСТИКА"]
        lines.append(admin.get_stats())
        lines.append(self.sensors.get_full_report())
        if self.iot_bridge:
            lines.append(self.iot_bridge.status())
        if self.mesh_net:
            lines.append(self.mesh_net.status_report())
        if self.gateway_mgr:
            lines.append(self.gateway_mgr.health_check())
        return "\n\n".join(lines)

    def _operator_recovery(self) -> str:
        lines = ["🛠️ ОПЕРАТОР: ВОССТАНОВЛЕНИЕ"]
        if self.gateway_mgr:
            lines.append(self.gateway_mgr.health_check())
        lines.append("Чек-лист:\n  1) Проверить порты/сеть\n  2) Переподготовить прошивку\n  3) Выполнить откат прошивки при деградации")
        return "\n\n".join(lines)

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
    гомеостаз статус · гомеостаз вкл/выкл
    любопытство статус · любопытство вкл/выкл · любопытство сейчас
        git статус · git коммит [msg] · git пуш · git автокоммит и пуш [msg]
        очередь статус · очередь результаты · очередь метрики
        в очередь [команда] [class=system|iot|ai|heavy priority=1..10 retries=N deadline=sec backoff=ms]
        очередь воркеры [n]

👁️ VISION (нужен Gemini API)
  посмотри на экран · что на экране
  посмотри в камеру · анализ фото [путь]

🤖 АГЕНТ (цепочки задач)
  статус → затем крипто → потом дайджест
  отчёт агента · останови агента

🧠 ПАМЯТЬ
  запомни [ключ]: [значение] · что ты знаешь
    найди в памяти [запрос] · поиск по памяти [запрос]
    граф знаний · связи памяти
  запиши заметку [название]: [текст]
  мои заметки · прочитай заметку [№]

⏰ РАСПИСАНИЕ
  каждые 2 часа [задача] · в 09:00 [задача]
  через 30 мин [задача] · расписание

🌐 P2P СЕТЬ
  статус сети · синхронизируй навыки
    p2p телеметрия · p2p tuning
    p2p вес [name] [value] · p2p failover [1..5]
  подключись к [IP] · распредели задачу [вопрос]
    p2p протокол · libp2p · zkp

🧠 TOOL CALLING
    схемы инструментов · json схемы инструментов

� УМНЫЕ СИСТЕМЫ
  умные системы · типы систем
  добавь систему [тип] [id]
  обнови сенсор [система] [сенсор] [значение]
  включи/выключи [актуатор] [система]
  добавь правило [система] если [условие] то [действие]
  Типы: home, greenhouse, garage, cellar, incubator, aquarium, terrarium

📡 IoT / MESH-СЕТЬ
    iot статус · iot возможности · добавь устройство [id] [тип] [протокол]
    статус устройства [id] · iot протоколы
    подключи zigbee/lora/mqtt/modbus · подключи modbus tcp [host] [port]
    modbus чтение [address] [count] [unit] · modbus запись [address] [value] [unit]
    запусти mesh
  статус mesh · запусти zigbee/lora [порт]
  запусти wifi mesh [SSID]
  добавь mesh устройство [id] [протокол] [адрес]
  mesh broadcast [протокол] [команда]
    найди usb чипы · умная прошивка [порт]
    Протоколы: BACnet, Modbus RTU/ASCII/TCP, KNX, LonWorks, M-Bus, OPC UA, MQTT
    Сети: Zigbee mesh, LoRa (SX1276), WiFi mesh

🔧 IoT ШЛЮЗЫ
  список шлюзов · шаблоны шлюзов
  создай шлюз [id] [шаблон]
    создай прошивку [id] [шаблон] [порт]
    изучи протокол [шаблон] [протокол] [прошивка] [описание]
    изучи устройство [шаблон] [протокол] [hardware]
  прошей шлюз [id] [порт] · прошей gateway [порт] [прошивка]
  конфиг шлюза [id]
    MCU: STM32H503, ESP8266, RP2040

🏠 HOME ASSISTANT
    ha статус · ha состояния
    ha сервис [domain] [service] [key=value]
    ha mqtt [topic] [key=value]

📡 NFC МЕТКИ
  nfc статус · nfc метки · nfc скан
  nfc регистрация [uid] [имя] [действие] [данные]
  nfc удали [uid]

🔌 USB ДИАГНОСТИКА
  usb статус · usb скан · usb устройства
  usb авторизованные

📶 BLUETOOTH СКАНЕР
  bt статус · bt инвентарь · bt скан [сек]
  bt iot

� AWA-CORE (КООРДИНАТОР)
  awa статус · awa модули · awa история · awa проверка

📊 ADAPTIVE DRAFTER (TLT)
  drafter статус · drafter метрики · drafter сброс кэша

🩺 SELF-HEALING
  healing статус · healing история · healing валидация

📻 AIRSNITCH (SDR/SUB-GHz)
  эфир статус · эфир скан · эфир монитор · эфир стоп
  эфир пакеты

🛡️ WIFI SENTINEL
  wifi статус · wifi скан · wifi ловушка · wifi ловушка стоп
  wifi монитор · wifi инциденты

🏠 SMARTHOME OVERRIDE
  smarthome статус · smarthome устройства · smarthome старт
  smarthome блокируй облако [id]

🔋 POWER SENTRY
  питание статус · питание старт · питание ups
  питание показания · аварийное отключение

🗑️ EMERGENCY PURGE
  purge статус · purge история
  purge запрос [logs|data|full] · purge подтверди [code]
  purge отмена

📦 CONTAINER ISOLATION
  контейнер статус · контейнер список
  контейнер запуск [module] · контейнер стоп [name]
  контейнер логи [name] · контейнер watchdog · контейнер очистка

🔐 АВТОРИЗАЦИЯ
  auth статус · auth ключ [мастер-ключ] · auth разлогин

🌿 БИОСФЕРА (DAG Bio-Control)
  биосфера статус · биосфера цикл · биосфера старт [сек]
  биосфера стоп · биосфера результат
  биосфера цель [ключ] [значение]

🌌 IBM QUANTUM
  ibm квантовый · квантовый мост

🧩 МОДУЛИ
    список модулей

🧠 LM STUDIO
    lmstudio статус

🎤 ГОЛОС
  голос вкл/выкл · включи wake word
    режим ии авто/gemini/gigachat/yandexgpt/lmstudio/ollama/watsonx

💬 ДИАЛОГ
  контекст диалога · сброс контекста
  история · помощь"""

    def _iot_protocols_help(self) -> str:
        return """🏭 ПОДДЕРЖИВАЕМЫЕ IoT/ПРОМ ПРОТОКОЛЫ:

    • BACnet (Building Automation and Control Networks)
    • Modbus RTU / ASCII / TCP
    • KNX
    • LonWorks (Local Operating Network)
    • M-Bus (Meter-Bus)
    • OPC UA (Open Platform Communications Unified Architecture)
    • MQTT

📡 Mesh и радио:
    • Zigbee mesh
    • LoRa mesh (включая SX1276)
    • WiFi mesh / gateway bridge

🔧 Прошивка устройств:
    • STM32H503, ESP8266, RP2040
    • Команды: создай прошивку [id] [шаблон] [порт]
                изучи протокол [шаблон] [протокол] [прошивка] [описание]
                изучи устройство [шаблон] [протокол] [hardware]"""

    def _start_smart_create_wizard(self) -> str:
        if not self.smart_sys:
            return "❌ Умные системы не инициализированы."

        self._smart_create_wizard = {
            "step": "type",
            "type": None,
            "id": None,
            "purpose": "",
            "functions": [],
        }
        types = ", ".join(self.smart_profiles.keys()) if self.smart_profiles else "home, greenhouse, garage, cellar, incubator, aquarium, terrarium"
        return (
            "🧭 Мастер создания умной системы.\n"
            "Шаг 1/4: выбери тип системы:\n"
            f"{types}\n"
            "Пример: greenhouse\n"
            "(для отмены: 'отмена')"
        )

    def _continue_smart_create_wizard(self, text: str) -> str:
        wiz = self._smart_create_wizard
        if not wiz:
            return None

        value = text.strip()
        step = wiz.get("step")

        if step == "type":
            sys_type = value.split()[0].lower()
            if sys_type not in self.smart_profiles:
                types = ", ".join(self.smart_profiles.keys())
                return f"❌ Неизвестный тип. Доступные: {types}\nВведи тип ещё раз."
            wiz["type"] = sys_type
            wiz["step"] = "id"
            profile = self.smart_profiles.get(sys_type, {})
            return (
                f"✅ Тип: {profile.get('icon','⚙️')} {profile.get('name', sys_type)}\n"
                "Шаг 2/4: задай ID системы (латиница/цифры), например: my_greenhouse\n"
                "Или напиши 'авто' для ID по умолчанию."
            )

        if step == "id":
            if value.lower() in ("авто", "auto", "default"):
                wiz["id"] = wiz["type"]
            else:
                wiz["id"] = value.split()[0]
            wiz["step"] = "purpose"
            return (
                f"✅ ID: {wiz['id']}\n"
                "Шаг 3/4: что система должна делать?\n"
                "Пример: поддерживать климат и безопасность, управлять поливом и вентиляцией."
            )

        if step == "purpose":
            wiz["purpose"] = value
            wiz["step"] = "functions"
            profile = self.smart_profiles.get(wiz["type"], {})
            actuators = ", ".join(profile.get("actuators", []))
            return (
                f"✅ Назначение: {wiz['purpose']}\n"
                "Шаг 4/4: какие функции включить сразу?\n"
                f"Доступные функции: {actuators}\n"
                "Введи через запятую (пример: irrigation, ventilation)\n"
                "или напиши 'авто' для стандартного профиля."
            )

        if step == "functions":
            profile = self.smart_profiles.get(wiz["type"], {})
            actuators = profile.get("actuators", [])
            if value.lower() not in ("авто", "auto", "default"):
                selected = [x.strip() for x in value.split(",") if x.strip()]
                valid = [x for x in selected if x in actuators]
                wiz["functions"] = valid
            else:
                wiz["functions"] = []

            create_msg = self.smart_sys.add_system(wiz["type"], wiz["id"])
            if create_msg.startswith("❌"):
                self._smart_create_wizard = None
                return create_msg

            if wiz["functions"]:
                for function_name in wiz["functions"]:
                    self.smart_sys.command(wiz["id"], function_name, "on")

            summary = (
                f"🧾 Создано: {wiz['type']} [{wiz['id']}]\n"
                f"🎯 Назначение: {wiz['purpose']}\n"
                f"🧩 Функции: {', '.join(wiz['functions']) if wiz['functions'] else 'стандартный профиль'}"
            )
            self._smart_create_wizard = None
            return f"{create_msg}\n\n{summary}"

        self._smart_create_wizard = None
        return "⚠️ Мастер сброшен. Запусти заново: 'создай умную систему'."

    def load_skill(self, name: str):
        if self.skill_loader:
            result = self.skill_loader.load(name, core=self)
            return self.skill_loader, result
        import importlib
        try:
            return importlib.import_module(f"src.skills.{name}"), f"✅ '{name}' загружен."
        except ModuleNotFoundError:
            return None, f"❌ '{name}' не найден."
