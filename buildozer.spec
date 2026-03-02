[app]

# ─── Основные параметры ─────────────────────────────────────────
title = Argos Universal OS
package.name = argos
package.domain = org.argos
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,md,env,ico,icns,ino
source.exclude_dirs = tests,docs,builds,build,dist,logs,__pycache__,.git,.github,data/chroma
source.exclude_patterns = *.pyc,*.pyo,*.bak,*.log

# ─── Точка входа ────────────────────────────────────────────────
# Buildozer ищет main.py в source.dir
# main.py --mobile → boot_mobile() → ArgosMobileUI (Kivy)

# ─── Версия ─────────────────────────────────────────────────────
version = 1.0.0
# version.regex = __version__ = ['"](.*)['"]
# version.filename = %(source.dir)s/main.py

# ─── Зависимости Python ─────────────────────────────────────────
requirements = python3,
    kivy==2.3.0,
    pillow,
    requests,
    certifi,
    urllib3,
    charset-normalizer,
    idna,
    pyjnius,
    android,
    plyer,
    cryptography,
    python-dotenv,
    psutil,
    beautifulsoup4,
    paho-mqtt,
    packaging,
    networkx

# ─── Android ────────────────────────────────────────────────────
android.permissions =
    INTERNET,
    ACCESS_NETWORK_STATE,
    ACCESS_WIFI_STATE,
    ACCESS_FINE_LOCATION,
    ACCESS_COARSE_LOCATION,
    NFC,
    BLUETOOTH,
    BLUETOOTH_ADMIN,
    BLUETOOTH_CONNECT,
    BLUETOOTH_SCAN,
    USB_PERMISSION,
    CAMERA,
    RECORD_AUDIO,
    READ_EXTERNAL_STORAGE,
    WRITE_EXTERNAL_STORAGE,
    RECEIVE_BOOT_COMPLETED,
    FOREGROUND_SERVICE,
    WAKE_LOCK,
    VIBRATE

android.api = 34
android.minapi = 26
android.ndk = 25b
android.sdk = 34
android.accept_sdk_license = True

# ─── Архитектура ────────────────────────────────────────────────
android.archs = arm64-v8a, armeabi-v7a

# ─── Фоновый сервис ─────────────────────────────────────────────
# android_service.py → ArgosOmniService (SensorBridge, NFC, BLE, USB)
services = ArgosService:src/connectivity/android_service.py:foreground

# ─── Ориентация и полноэкранность ───────────────────────────────
orientation = portrait
fullscreen = 0

# ─── Иконка и пресплеш ──────────────────────────────────────────
# icon.filename = %(source.dir)s/assets/argos_icon.png
# presplash.filename = %(source.dir)s/assets/argos_splash.png

# ─── Логирование ────────────────────────────────────────────────
android.logcat_filters = *:S python:D

# ─── Gradle ─────────────────────────────────────────────────────
android.gradle_dependencies =
android.enable_androidx = True
android.add_aars =
android.add_jars =

# ─── Прочее ─────────────────────────────────────────────────────
# Отключаем presplash по умолчанию
# presplash.color = #1a1a2e

# Копируем .env если есть
# android.add_src =

# ─── p4a (python-for-android) ───────────────────────────────────
p4a.branch = develop
# p4a.source_dir =
# p4a.local_recipes =
# p4a.hook =
# p4a.bootstrap = sdl2

# ─── Buildozer ──────────────────────────────────────────────────
log_level = 2
warn_on_root = 1

# ─── iOS (заглушка) ─────────────────────────────────────────────
# ios.kivy_ios_url = https://github.com/kivy/kivy-ios
# ios.kivy_ios_branch = master
# ios.ios_deploy_url = https://github.com/nicknisi/ios-deploy
# ios.ios_deploy_branch = 1.10.0

[buildozer]
log_level = 2
warn_on_root = 1
