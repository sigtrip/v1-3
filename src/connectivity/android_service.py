"""
android_service.py — Фоновый сервис Android
  Запускается при загрузке устройства, держит Аргоса активным.
  Работает в уведомлении статуса даже когда приложение свёрнуто.
"""
import os
import time

def main():
    """Точка входа фонового сервиса."""
    try:
        from jnius import autoclass
        # Android Service API
        PythonService = autoclass('org.kivy.android.PythonService')
        PythonService.mService.setAutoRestartService(True)  # Перезапуск при падении
    except Exception:
        pass  # Не Android — пропуск

    print("[ARGOS SERVICE]: Фоновый страж активирован.")

    # Загружаем .env и запускаем мониторинг
    try:
        from dotenv import load_dotenv
        load_dotenv()

        from src.connectivity.sensor_bridge import ArgosSensorBridge
        sensors = ArgosSensorBridge()

        check_interval = 30  # секунд
        while True:
            report = sensors.get_full_report()
            print(f"[ARGOS PATROL]: {report}")
            time.sleep(check_interval)
    except Exception as e:
        print(f"[ARGOS SERVICE ERROR]: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
