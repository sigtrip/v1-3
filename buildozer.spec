
[app]
# (str) Название приложения
title = ARGOS OS

# (str) Имя пакета
package.name = argos_v13

# (str) Домен пакета (используется для ID приложения)
package.domain = org.sigtrip

# (str) Папка с исходным кодом (текущая)
source.dir = .

# (list) Расширения файлов, которые будут включены в билд
source.include_exts = py,png,jpg,kv,atlas,txt

# (str) Версия приложения
version = 1.3.4

# (list) Зависимости приложения. 
# Включаем pyjnius для доступа к Android API и requests для ИИ.
requirements = python3,kivy,requests,urllib3,certifi,idna,charset-normalizer,pyjnius

# (str) Ориентация экрана
orientation = portrait

# (bool) Полноэкранный режим
fullscreen = 0

# (list) РАЗРЕШЕНИЯ ANDROID. 
# INTERNET: для связи с Ollama
# BLUETOOTH/LOCATION: для функций в стиле Flipper (сканирование)
# NFC: для чтения меток
# STORAGE: для сохранения данных
android.permissions = INTERNET, BLUETOOTH, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, NFC, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, QUERY_ALL_PACKAGES

# (int) Android API (33 — современный стандарт, 31 — минимальный для Google Play сейчас)
android.api = 33

# (int) Минимальный API (21 — поддержка Android 5.0 и выше)
android.minapi = 21

# (str) Версия Android NDK (25b проверена и стабильна)
android.ndk = 25b

# (bool) Автоматически принимать лицензии SDK
android.accept_sdk_license = True

# (list) Архитектуры (arm64 — для новых телефонов, armeabi — для старых)
android.archs = arm64-v8a, armeabi-v7a

# (str) Тип загрузчика
android.bootstrap = sdl2

[buildozer]
# (int) Уровень логов (2 — подробный, помогает искать ошибки)
log_level = 2

# (int) Предупреждать о запуске под ROOT (в Colab ставим 0, чтобы не мешало)
warn_on_root = 0
