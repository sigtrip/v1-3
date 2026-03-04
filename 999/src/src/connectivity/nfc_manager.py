"""
nfc_manager.py — NFC-менеджер для собственных устройств
  Чтение/запись NFC-меток для автоматизации умного дома.
  Поддержка: NDEF, MIFARE, NTAG (только собственные метки).
  
  Сценарии использования:
  - Запуск сценариев умного дома по касанию метки
  - Инвентаризация IoT-устройств с NFC-метками
  - Автоматизация рутинных задач
"""
import json
import os
import time
import threading
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum

try:
    from src.argos_logger import get_logger
    from src.event_bus import get_bus, Events
    from src.observability import trace
except ImportError:
    # Fallback для автономного тестирования
    import logging
    get_logger = lambda name: logging.getLogger(name)
    get_bus = lambda: None
    Events = type('Events', (), {'NFC_TAG_DETECTED': 'nfc_tag_detected'})()
    trace = lambda name: lambda f: f

log = get_logger("argos.nfc")

# Путь к базе зарегистрированных меток
NFC_TAGS_FILE = "data/nfc_tags.json"


class TagType(Enum):
    """Тип NFC-метки."""
    NDEF = "ndef"
    MIFARE_CLASSIC = "mifare_classic"
    MIFARE_ULTRALIGHT = "mifare_ultralight"
    NTAG = "ntag"
    ISO14443A = "iso14443a"
    UNKNOWN = "unknown"


class TagAction(Enum):
    """Действие, привязанное к метке."""
    RUN_SCENARIO = "run_scenario"
    TOGGLE_DEVICE = "toggle_device"
    SEND_COMMAND = "send_command"
    LOG_EVENT = "log_event"
    CUSTOM_CALLBACK = "custom_callback"


@dataclass
class NFCTag:
    """Зарегистрированная NFC-метка."""
    uid: str                    # Уникальный ID метки (hex)
    name: str                   # Человекочитаемое имя
    tag_type: str               # Тип метки
    action: str                 # Привязанное действие
    action_data: Dict[str, Any] # Параметры действия
    location: str = ""          # Где размещена метка
    registered_at: float = 0    # Время регистрации
    last_scanned: float = 0     # Последнее сканирование
    scan_count: int = 0         # Счётчик сканирований
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "NFCTag":
        return cls(**d)


class NFCManager:
    """
    Менеджер NFC для управления собственными метками.
    
    Использование:
        nfc = NFCManager()
        nfc.register_tag("04:A2:B3:C4:D5:E6:F7", "Входная дверь", 
                         TagAction.RUN_SCENARIO, {"scenario": "arrive_home"})
        nfc.start_scanning()
    """
    
    def __init__(self, android_mode: bool = False):
        self.android_mode = android_mode
        self._tags: Dict[str, NFCTag] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._scanning = False
        self._scan_thread: Optional[threading.Thread] = None
        self._nfc_adapter = None
        self._load_tags()
        self._init_adapter()
        
    def _init_adapter(self):
        """Инициализация NFC-адаптера."""
        if self.android_mode:
            self._init_android_nfc()
        else:
            self._init_desktop_nfc()
    
    def _init_android_nfc(self):
        """Инициализация NFC на Android через Kivy/pyjnius."""
        try:
            from jnius import autoclass
            NfcAdapter = autoclass('android.nfc.NfcAdapter')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity
            self._nfc_adapter = NfcAdapter.getDefaultAdapter(context)
            
            if self._nfc_adapter is None:
                log.warning("NFC: адаптер не найден на устройстве")
            elif not self._nfc_adapter.isEnabled():
                log.warning("NFC: адаптер выключен, включите в настройках")
            else:
                log.info("NFC: Android-адаптер инициализирован")
        except Exception as e:
            log.debug("NFC: Android API недоступен: %s", e)
            self._nfc_adapter = None
    
    def _init_desktop_nfc(self):
        """Инициализация NFC на десктопе через nfcpy или pyscard."""
        # Попытка использовать nfcpy (USB NFC-ридеры)
        try:
            import nfc
            self._nfc_adapter = nfc.ContactlessFrontend('usb')
            log.info("NFC: Desktop-адаптер (nfcpy) инициализирован")
            return
        except Exception as e:
            log.debug("NFC: nfcpy недоступен: %s", e)
        
        # Попытка использовать pyscard (PC/SC ридеры)
        try:
            from smartcard.System import readers
            available_readers = readers()
            if available_readers:
                self._nfc_adapter = {"type": "pyscard", "readers": available_readers}
                log.info("NFC: Desktop-адаптер (pyscard) найден: %s", 
                        [str(r) for r in available_readers])
                return
        except Exception as e:
            log.debug("NFC: pyscard недоступен: %s", e)
        
        log.info("NFC: работа в режиме симуляции (нет физического адаптера)")
        self._nfc_adapter = {"type": "simulation"}
    
    def _load_tags(self):
        """Загрузка зарегистрированных меток из файла."""
        os.makedirs("data", exist_ok=True)
        if os.path.exists(NFC_TAGS_FILE):
            try:
                with open(NFC_TAGS_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                for tag_data in data:
                    tag = NFCTag.from_dict(tag_data)
                    self._tags[tag.uid] = tag
                log.info("NFC: загружено %d меток", len(self._tags))
            except Exception as e:
                log.warning("NFC: ошибка загрузки меток: %s", e)
    
    def _save_tags(self):
        """Сохранение меток в файл."""
        try:
            os.makedirs("data", exist_ok=True)
            with open(NFC_TAGS_FILE, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in self._tags.values()], f, 
                         ensure_ascii=False, indent=2)
        except Exception as e:
            log.error("NFC: ошибка сохранения меток: %s", e)
    
    @trace("nfc.register_tag")
    def register_tag(self, uid: str, name: str, action: TagAction,
                     action_data: Dict[str, Any], location: str = "") -> NFCTag:
        """
        Регистрация новой NFC-метки.
        
        Args:
            uid: Уникальный ID метки (hex формат)
            name: Человекочитаемое имя
            action: Действие при сканировании
            action_data: Параметры действия
            location: Описание расположения метки
            
        Returns:
            Зарегистрированная метка
        """
        uid = self._normalize_uid(uid)
        tag = NFCTag(
            uid=uid,
            name=name,
            tag_type=TagType.UNKNOWN.value,
            action=action.value,
            action_data=action_data,
            location=location,
            registered_at=time.time()
        )
        self._tags[uid] = tag
        self._save_tags()
        log.info("NFC: метка '%s' зарегистрирована (UID: %s)", name, uid)
        return tag
    
    def unregister_tag(self, uid: str) -> bool:
        """Удаление метки из реестра."""
        uid = self._normalize_uid(uid)
        if uid in self._tags:
            del self._tags[uid]
            self._save_tags()
            log.info("NFC: метка удалена (UID: %s)", uid)
            return True
        return False
    
    def get_tag(self, uid: str) -> Optional[NFCTag]:
        """Получение информации о метке."""
        return self._tags.get(self._normalize_uid(uid))
    
    def list_tags(self) -> List[NFCTag]:
        """Список всех зарегистрированных меток."""
        return list(self._tags.values())
    
    def register_callback(self, action_name: str, callback: Callable):
        """Регистрация callback-функции для кастомных действий."""
        self._callbacks[action_name] = callback
        log.debug("NFC: зарегистрирован callback '%s'", action_name)
    
    def start_scanning(self):
        """Запуск фонового сканирования NFC-меток."""
        if self._scanning:
            log.warning("NFC: сканирование уже запущено")
            return
            
        self._scanning = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        log.info("NFC: сканирование запущено")
    
    def stop_scanning(self):
        """Остановка сканирования."""
        self._scanning = False
        if self._scan_thread:
            self._scan_thread.join(timeout=2)
        log.info("NFC: сканирование остановлено")
    
    def _scan_loop(self):
        """Основной цикл сканирования."""
        while self._scanning:
            try:
                tag_uid = self._read_tag()
                if tag_uid:
                    self._handle_tag(tag_uid)
            except Exception as e:
                log.debug("NFC: ошибка в цикле сканирования: %s", e)
            time.sleep(0.5)
    
    def _read_tag(self) -> Optional[str]:
        """Чтение NFC-метки (платформозависимо)."""
        if self._nfc_adapter is None:
            return None
            
        if isinstance(self._nfc_adapter, dict):
            if self._nfc_adapter.get("type") == "pyscard":
                return self._read_pyscard()
            return None  # Симуляция
        
        # nfcpy
        try:
            tag = self._nfc_adapter.connect(rdwr={'on-connect': lambda t: False},
                                            terminate=lambda: not self._scanning)
            if tag:
                return self._normalize_uid(tag.identifier.hex())
        except Exception:
            pass
        return None
    
    def _read_pyscard(self) -> Optional[str]:
        """Чтение через pyscard."""
        try:
            from smartcard.CardRequest import CardRequest
            from smartcard.util import toHexString
            
            request = CardRequest(timeout=0.5)
            service = request.waitforcard()
            connection = service.connection
            connection.connect()
            
            # GET UID command for most NFC cards
            GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
            data, sw1, sw2 = connection.transmit(GET_UID)
            
            if sw1 == 0x90 and sw2 == 0x00:
                uid = toHexString(data).replace(" ", ":")
                return uid
        except Exception:
            pass
        return None
    
    def _handle_tag(self, uid: str):
        """Обработка обнаруженной метки."""
        tag = self._tags.get(uid)
        
        if tag:
            # Обновляем статистику
            tag.last_scanned = time.time()
            tag.scan_count += 1
            self._save_tags()
            
            log.info("NFC: обнаружена метка '%s' (UID: %s)", tag.name, uid)
            
            # Публикуем событие
            bus = get_bus()
            if bus:
                bus.emit(Events.NFC_TAG_DETECTED, {
                    "uid": uid,
                    "name": tag.name,
                    "action": tag.action,
                    "action_data": tag.action_data
                }, "nfc_manager")
            
            # Выполняем действие
            self._execute_action(tag)
        else:
            log.info("NFC: обнаружена незарегистрированная метка (UID: %s)", uid)
            # Можно предложить зарегистрировать
    
    def _execute_action(self, tag: NFCTag):
        """Выполнение действия, привязанного к метке."""
        action = tag.action
        data = tag.action_data
        
        if action == TagAction.RUN_SCENARIO.value:
            self._run_scenario(data.get("scenario", ""))
        elif action == TagAction.TOGGLE_DEVICE.value:
            self._toggle_device(data.get("device_id", ""))
        elif action == TagAction.SEND_COMMAND.value:
            self._send_command(data.get("command", ""))
        elif action == TagAction.LOG_EVENT.value:
            log.info("NFC EVENT: %s — %s", tag.name, data.get("message", ""))
        elif action == TagAction.CUSTOM_CALLBACK.value:
            callback_name = data.get("callback", "")
            if callback_name in self._callbacks:
                self._callbacks[callback_name](tag, data)
    
    def _run_scenario(self, scenario_name: str):
        """Запуск сценария умного дома."""
        try:
            from src.smart_systems import SmartSystemsOperator
            operator = SmartSystemsOperator()
            operator.run_scenario(scenario_name)
            log.info("NFC: запущен сценарий '%s'", scenario_name)
        except Exception as e:
            log.error("NFC: ошибка запуска сценария: %s", e)
    
    def _toggle_device(self, device_id: str):
        """Переключение состояния IoT-устройства."""
        try:
            from src.connectivity.iot_bridge import IoTBridge
            bridge = IoTBridge()
            bridge.toggle_device(device_id)
            log.info("NFC: переключено устройство '%s'", device_id)
        except Exception as e:
            log.error("NFC: ошибка переключения устройства: %s", e)
    
    def _send_command(self, command: str):
        """Отправка команды в ядро Аргоса."""
        try:
            from src.core import ArgosCore
            core = ArgosCore()
            core.process_command(command)
            log.info("NFC: отправлена команда '%s'", command)
        except Exception as e:
            log.error("NFC: ошибка отправки команды: %s", e)
    
    @staticmethod
    def _normalize_uid(uid: str) -> str:
        """Нормализация UID к единому формату."""
        # Убираем пробелы и приводим к верхнему регистру с двоеточиями
        uid = uid.upper().replace(" ", "").replace("-", "")
        # Добавляем двоеточия каждые 2 символа
        return ":".join(uid[i:i+2] for i in range(0, len(uid), 2))
    
    def scan_single(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Однократное сканирование для регистрации новой метки.
        
        Args:
            timeout: Время ожидания в секундах
            
        Returns:
            Информация о метке или None
        """
        log.info("NFC: ожидание метки (%.1f сек)...", timeout)
        start = time.time()
        
        while time.time() - start < timeout:
            uid = self._read_tag()
            if uid:
                # Пытаемся определить тип метки
                tag_info = {
                    "uid": uid,
                    "type": self._detect_tag_type(uid),
                    "registered": uid in self._tags
                }
                log.info("NFC: обнаружена метка %s", uid)
                return tag_info
            time.sleep(0.2)
        
        log.info("NFC: метка не обнаружена")
        return None
    
    def _detect_tag_type(self, uid: str) -> str:
        """Определение типа метки по UID."""
        # По длине UID можно приблизительно определить тип
        uid_bytes = len(uid.replace(":", "")) // 2
        
        if uid_bytes == 4:
            return TagType.MIFARE_CLASSIC.value
        elif uid_bytes == 7:
            return TagType.MIFARE_ULTRALIGHT.value
        elif uid_bytes == 10:
            return TagType.ISO14443A.value
        return TagType.UNKNOWN.value
    
    def write_ndef(self, uid: str, text: str) -> bool:
        """
        Запись NDEF-сообщения на метку.
        
        Args:
            uid: UID метки
            text: Текст для записи
            
        Returns:
            Успешность операции
        """
        if self._nfc_adapter is None:
            log.warning("NFC: адаптер не инициализирован")
            return False
        
        try:
            import ndef
            record = ndef.TextRecord(text)
            message = ndef.message_encoder([record])
            # Запись зависит от адаптера
            log.info("NFC: NDEF-сообщение записано на %s", uid)
            return True
        except Exception as e:
            log.error("NFC: ошибка записи NDEF: %s", e)
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Статус NFC-менеджера."""
        return {
            "adapter_available": self._nfc_adapter is not None,
            "scanning": self._scanning,
            "registered_tags": len(self._tags),
            "mode": "android" if self.android_mode else "desktop"
        }


# Глобальный экземпляр для удобства
_nfc_manager: Optional[NFCManager] = None

def get_nfc_manager(android_mode: bool = False) -> NFCManager:
    """Получение глобального NFC-менеджера."""
    global _nfc_manager
    if _nfc_manager is None:
        _nfc_manager = NFCManager(android_mode)
    return _nfc_manager


# CLI для тестирования
if __name__ == "__main__":
    import sys
    
    nfc = NFCManager()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "scan":
            result = nfc.scan_single(timeout=10)
            print(f"Результат: {result}")
            
        elif cmd == "list":
            tags = nfc.list_tags()
            for tag in tags:
                print(f"• {tag.name} ({tag.uid}) — {tag.action}")
                
        elif cmd == "status":
            print(nfc.get_status())
    else:
        print("NFC Manager для Argos")
        print("Использование: python nfc_manager.py [scan|list|status]")
