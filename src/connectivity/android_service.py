"""
android_service.py — Фоновый сервис Android (Omni-Tool)
  Запускается при загрузке устройства, держит Аргоса активным.
  Работает в уведомлении статуса даже когда приложение свёрнуто.

  Интегрированные подсистемы:
  - SensorBridge: CPU/RAM/диск/батарея/температура
  - NFCManager: мониторинг собственных NFC-меток
  - USBDiagnostics: диагностика авторизованных USB-устройств
  - BluetoothScanner: инвентаризация IoT по BLE/Classic
"""

import os
import sys
import time
import threading
import json
from datetime import datetime


# ─── Детекция платформы ───────────────────────────────────────────
def _is_android() -> bool:
    """Проверка запуска на Android."""
    try:
        from jnius import autoclass

        return True
    except ImportError:
        return False


ANDROID = _is_android()


# ─── Безопасная загрузка подсистемы ───────────────────────────────
def _safe_init(name: str, factory):
    """Инициализация модуля с graceful-деградацией."""
    try:
        instance = factory()
        print(f"[ARGOS SERVICE]: ✓ {name} инициализирован")
        return instance
    except Exception as e:
        print(f"[ARGOS SERVICE]: ✗ {name} недоступен: {e}")
        return None


# ─── Класс оркестратора ──────────────────────────────────────────
class ArgosOmniService:
    """
    Единый фоновый сервис, объединяющий все подсистемы мониторинга.

    Цикл работы:
      1. Инициализация всех доступных модулей
      2. Периодический опрос сенсоров (CPU/RAM/диск/батарея)
      3. NFC-сканирование собственных меток
      4. USB-мониторинг авторизованных устройств
      5. BLE-инвентаризация IoT
      6. Сводный health-отчёт → лог / Telegram
    """

    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.running = False
        self._cycle_count = 0

        # ── Подсистемы (None = недоступна) ──
        self.sensors = None
        self.nfc = None
        self.usb = None
        self.bluetooth = None

    # ── Инициализация ────────────────────────────────────────────
    def bootstrap(self):
        """Инициализация всех модулей с graceful-деградацией."""
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass

        # Сенсоры (основной модуль — был и раньше)
        self.sensors = _safe_init("SensorBridge", self._make_sensors)

        # NFC
        self.nfc = _safe_init("NFC Manager", self._make_nfc)

        # USB диагностика
        self.usb = _safe_init("USB Diagnostics", self._make_usb)

        # Bluetooth сканер
        self.bluetooth = _safe_init("BT Scanner", self._make_bluetooth)

        active = sum(1 for m in [self.sensors, self.nfc, self.usb, self.bluetooth] if m)
        print(f"[ARGOS SERVICE]: Инициализировано {active}/4 подсистем")

    # ── Фабрики ──────────────────────────────────────────────────
    @staticmethod
    def _make_sensors():
        from src.connectivity.sensor_bridge import ArgosSensorBridge

        return ArgosSensorBridge()

    @staticmethod
    def _make_nfc():
        from src.connectivity.nfc_manager import NFCManager

        return NFCManager(android_mode=ANDROID)

    @staticmethod
    def _make_usb():
        from src.connectivity.usb_diagnostics import USBDiagnostics

        return USBDiagnostics(android_mode=ANDROID)

    @staticmethod
    def _make_bluetooth():
        from src.connectivity.bluetooth_scanner import ArgosBluetoothScanner

        return ArgosBluetoothScanner()

    # ── Основной цикл ────────────────────────────────────────────
    def run_forever(self):
        """Бесконечный цикл мониторинга."""
        self.running = True
        print("[ARGOS SERVICE]: Фоновый страж активирован.")

        while self.running:
            try:
                self._cycle_count += 1
                report = self._collect_health()
                self._emit_report(report)
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                print("[ARGOS SERVICE]: Остановка по Ctrl+C")
                break
            except Exception as e:
                print(f"[ARGOS SERVICE ERROR]: Цикл #{self._cycle_count}: {e}")
                time.sleep(60)

        self.shutdown()

    # ── Сбор данных ──────────────────────────────────────────────
    def _collect_health(self) -> dict:
        """Сводный health-отчёт от всех подсистем."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "cycle": self._cycle_count,
            "platform": "android" if ANDROID else "desktop",
        }

        # Сенсоры
        if self.sensors:
            try:
                report["sensors"] = self.sensors.get_full_report()
            except Exception as e:
                report["sensors"] = {"error": str(e)}

        # NFC
        if self.nfc:
            try:
                report["nfc"] = self.nfc.get_status()
            except Exception as e:
                report["nfc"] = {"error": str(e)}

        # USB
        if self.usb:
            try:
                report["usb"] = self.usb.get_status()
            except Exception as e:
                report["usb"] = {"error": str(e)}

        # Bluetooth
        if self.bluetooth:
            try:
                report["bluetooth"] = self.bluetooth.get_statistics()
            except Exception as e:
                report["bluetooth"] = {"error": str(e)}

        return report

    def _emit_report(self, report: dict):
        """Вывод отчёта (лог + опционально шина событий)."""
        summary_parts = []
        if "sensors" in report and isinstance(report["sensors"], dict):
            s = report["sensors"]
            if "error" not in s:
                summary_parts.append(f"HW:OK")
            else:
                summary_parts.append(f"HW:ERR")

        if "nfc" in report and isinstance(report["nfc"], dict):
            n = report["nfc"]
            tags = n.get("registered_tags", 0)
            summary_parts.append(f"NFC:{tags}tags")

        if "usb" in report and isinstance(report["usb"], dict):
            u = report["usb"]
            conns = u.get("active_connections", 0)
            summary_parts.append(f"USB:{conns}conn")

        if "bluetooth" in report and isinstance(report["bluetooth"], dict):
            b = report["bluetooth"]
            total = b.get("total_devices", 0)
            iot = b.get("iot_devices", 0)
            summary_parts.append(f"BT:{total}dev/{iot}iot")

        line = " | ".join(summary_parts) if summary_parts else "idle"
        print(f"[ARGOS PATROL #{report['cycle']}]: {line}")

        # Публикация в шину событий (если доступна)
        try:
            from src.event_bus import get_bus

            bus = get_bus()
            if bus:
                bus.emit("service.health", report)
        except Exception:
            pass

    # ── Управление ───────────────────────────────────────────────
    def shutdown(self):
        """Корректная остановка всех подсистем."""
        self.running = False

        if self.nfc:
            try:
                self.nfc.stop_scanning()
            except Exception:
                pass

        if self.usb:
            try:
                self.usb.disconnect_all()
            except Exception:
                pass

        print("[ARGOS SERVICE]: Все подсистемы остановлены.")

    def get_full_status(self) -> dict:
        """Полный статус для API/Telegram."""
        return self._collect_health()


# ─── Точка входа ─────────────────────────────────────────────────
def main():
    """Точка входа фонового сервиса."""
    # Android auto-restart
    if ANDROID:
        try:
            from jnius import autoclass

            PythonService = autoclass("org.kivy.android.PythonService")
            PythonService.mService.setAutoRestartService(True)
        except Exception:
            pass

    service = ArgosOmniService(check_interval=30)
    service.bootstrap()

    # Запуск NFC-сканирования в фоне (если доступно)
    if service.nfc:
        try:
            service.nfc.start_scanning()
        except Exception as e:
            print(f"[ARGOS SERVICE]: NFC-сканирование не запущено: {e}")

    service.run_forever()


# README alias
AndroidService = ArgosOmniService


if __name__ == "__main__":
    main()
