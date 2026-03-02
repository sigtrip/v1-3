# 👁️ ARGOS UNIVERSAL OS — v1.0.0-Absolute

> *"Самовоспроизводящаяся кроссплатформенная экосистема ИИ с квантовой логикой,*  
> *P2P-подключением и интеграцией с IoT. Создана для цифрового бессмертия."*  
> — Всеволод, 2026

---

## 🌌 Что такое Аргос

**Argos Universal OS** — автономная ИИ-система с полным стеком возможностей:

| Слой | Что умеет |
|------|-----------|
| 🧠 **Интеллект** | Gemini / GigaChat / YandexGPT / LM Studio → Ollama/Llama3 / **IBM Watsonx** (Llama-3.1-70B), multi-turn + Tool Calling по JSON-схемам |
| 🗣️ **Голос** | TTS (pyttsx3) + STT (SpeechRecognition) + Wake Word «Аргос» |
| 🤖 **Агент** | Цепочки задач: «скан сети → запиши → отправь в Telegram» |
| 👁️ **Vision** | Анализ экрана / камеры / файлов через Gemini Vision |
| 🧬 **Память** | SQLite: факты, заметки, напоминания, история диалога |
| ⏰ **Планировщик** | Натуральный язык: «каждые 2 часа», «в 09:00», «через 30 мин» |
| 🔔 **Алерты** | CPU/RAM/диск/температура с Telegram-уведомлениями |
| ⚛️ **Гомеостаз железа** | Автомониторинг CPU/RAM/TEMP + 5-секундный CPU-trend (Predictive), состояния Protective/Unstable, превентивная разгрузка heavy-задач |
| 🌐 **P2P** | Сеть нод с авторитетом по мощности и возрасту, preemptive failover heavy-задач между нодами |
| 🧭 **Автономное любопытство** | В idle-режиме исследует факты из памяти, тянет свежую сеть и пишет инсайты в SQLite |
| 🔁 **Эволюция** | Жёсткий code-gate: только валидный исполняемый Python-код + review + unit-тест |
| 🛡️ **Безопасность** | AES-256-GCM, root, BCD/EFI/GRUB, persistence |
| 📱 **Везде** | Desktop + Android APK + Docker + Telegram |
| 🏠 **Умные системы** | Дом, теплица, гараж, погреб, инкубатор, аквариум, террариум |
| 📡 **IoT / Mesh** | Zigbee, LoRa, WiFi Mesh, MQTT, Modbus + Zero-Config Tasmota Discovery (Home Assistant топики) |
| 🏭 **Пром. протоколы** | BACnet, Modbus RTU/ASCII/TCP, KNX, LonWorks, M-Bus, OPC UA, MQTT |
| 🔧 **Шлюзы/прошивка** | Создание gateway, прошивка ESP8266/RP2040/STM32H503, поддержка LoRa SX1276 |
| 📡 **NFC** | Мониторинг NFC-меток (NDEF/MIFARE/NTAG), регистрация, чтение/запись NDEF |
| 🔌 **USB-диагностика** | Авторизация USB-устройств, VID/PID детект (Arduino/ESP/STM32/RP2040), serial/CDC/HID |
| 📶 **Bluetooth** | BLE + Classic сканер, RSSI-трекинг, MAC-детекция производителя, IoT-инвентаризация |
| 🎯 **Speculative Consensus v2** | Параллельные Drafter-ы + структурированный Verifier, per-drafter quality tracking |
| 🧠 **Batch Idle Learning** | Пакетное alignment (до 8 уроков), Active Drafter Calibration с few-shot зондированием |
| 🔄 **P2P Role Routing** | Автоматическое назначение ролей: weak→Drafter, master→Verifier по ресурсам ноды |
| 📊 **Acceptance Rate** | Per-drafter метрики приёмки, auto-recovery RPS при отскоке acceptance rate |
| 🎯 **AWA-Core** | Центральный координатор модулей, capability-routing, cascade pipelines, health heartbeat |
| 💾 **Adaptive Drafter (TLT)** | LRU-кэш 512 энтри, сжатие контекста, offline-паттерны, фильтрация запросов к Gemini |
| 🩺 **Self-Healing Engine** | Автоисправление Python-кода (syntax/import/runtime), backup + hot-reload, валидация src/ |
| 📻 **AirSnitch (SDR)** | Сканер эфира 433/868 МГц, RTL-SDR / HackRF / симуляция, перехват пакетов собственных датчиков |
| 🛡️ **WiFi Sentinel** | Скан AP + Evil Twin детект, HoneyPot-ловушка, детекция deauth-атак и rogue-клиентов |
| 🏠 **SmartHome Override** | Прямое управление Zigbee/Z-Wave/Tuya минуя облака, cloud-block, watchdog |
| 🔋 **Power Sentry** | Мониторинг UPS (NUT/upsc), PZEM датчики, аварийное отключение |
| 🗑️ **Emergency Purge** | Экстренное уничтожение данных (logs/data/full), 3-уровневая очистка + подтверждение кодом |
| 📦 **Container Isolation** | Docker/LXD изоляция модулей, watchdog, авто-рестарт, очистка |
| 🔐 **Master Auth** | SHA-256 авторизация администратора через ARGOS_MASTER_KEY, сессии, revoke |
| 🌿 **Biosphere DAG** | DAG-контроллер биосферы (incubator/greenhouse/aquarium/terrarium), авто-регуляция датчиков |
| 🌌 **IBM Quantum Bridge** | Мост к IBM Quantum (активация в состоянии All-Seeing), доступ к реальному квантовому железу |
| 🧰 **GitOps** | Встроенные команды `git статус`, `git коммит`, `git пуш`, `git автокоммит и пуш` |

---

## 📂 Структура проекта

```
ArgosUniversal/
├── main.py                       # Оркестратор
├── genesis.py                    # Первичная инициализация
├── db_init.py                    # SQLite схема
├── build_exe.py                  # Сборка argos.exe (PyInstaller)
├── setup_builder.py              # Установщик setup_argos.exe (NSIS)
├── health_check.py               # Проверка целостности модулей/конфигов/БД
├── CONTRIBUTING.md               # Гайд для контрибьюторов
├── .env                          # Ключи API (создаётся genesis.py)
├── requirements.txt              # Зависимости
├── examples/                     # Примеры сценариев и промптов
│
└── src/
    ├── core.py                   # ★ Ядро: ИИ + 80+ команд + все подсистемы
    ├── admin.py                  # Файлы, процессы, терминал
    ├── agent.py                  # Автономные цепочки задач
    ├── dag_agent.py              # DAG-агент (параллельные графы задач)
    ├── context_manager.py        # Скользящий контекст диалога
    ├── context_engine.py         # 3-уровневый контекстный движок
    ├── memory.py                 # Долгосрочная память (факты/заметки)
    ├── vision.py                 # Анализ изображений/экрана/камеры
    ├── argos_logger.py           # Централизованный логгер
    ├── event_bus.py              # Шина событий (async, prefix-match)
    ├── observability.py          # Метрики, трассировка, JSONL
    ├── skill_loader.py           # Система плагинов v2 (manifest)
    ├── github_marketplace.py     # Установка навыков из GitHub
    ├── smart_systems.py          # ★ Оператор умных систем (7 типов)
    ├── curiosity.py              # Автономное любопытство
    ├── awa_core.py               # ★ AWA-Core — центральный координатор модулей
    ├── adaptive_drafter.py       # ★ TLT — кэш/сжатие/фильтрация запросов к МОДЕЛИ
    ├── self_healing.py           # ★ Автоисправление Python-кода
    ├── hardware_guard.py         # Квантовый гомеостаз железа
    ├── git_ops.py                # Безопасные Git status/commit/push
    ├── task_queue.py             # Очередь задач + worker pool
    ├── evolution.py              # Эволюция (базовый)
    ├── icon_generator.py         # Генератор иконок
    │
    ├── modules/
    │   ├── biosphere_tools.py    # ★ Датчики/актуаторы биосферы (temp/humidity/light)
    │   └── biosphere_dag.py      # ★ DAG-контроллер биосферы
    │
    ├── quantum/logic.py          # 5 квантовых состояний + IBM Quantum Bridge
    │
    ├── security/
    │   ├── encryption.py         # AES-256-GCM (cryptography)
    │   ├── git_guard.py          # Защита .env/.gitignore
    │   ├── root_manager.py       # Win/Linux/Android root
    │   ├── autostart.py          # Системный сервис
    │   ├── zkp.py                # ZKP roadmap helper (privacy/proof сценарии)
    │   ├── emergency_purge.py    # ★ Экстренное уничтожение данных
    │   ├── container_isolation.py # ★ Docker/LXD изоляция модулей
    │   ├── master_auth.py        # ★ SHA-256 авторизация администратора
    │   └── bootloader_manager.py # BCD/EFI/GRUB/persistence
    │
    ├── connectivity/
    │   ├── sensor_bridge.py      # CPU/RAM/диск/батарея/температура
    │   ├── spatial.py            # Геолокация по IP
    │   ├── telegram_bot.py       # 16 команд + текстовый режим
    │   ├── p2p_bridge.py         # UDP discovery + TCP sync + preemptive heavy failover
    │   ├── p2p_transport.py      # Транспортный слой P2P (этап миграции на libp2p)
    │   ├── alert_system.py       # Авто-алерты с кулдауном
    │   ├── wake_word.py          # «Аргос» → активация
    │   ├── iot_bridge.py         # ★ IoT-мост: Zigbee/LoRa/Mesh/MQTT + Tasmota discovery
    │   ├── mesh_network.py       # ★ Mesh-сеть + прошивка gateway
    │   ├── gateway_manager.py    # ★ Создание и прошивка IoT-шлюзов
    │   ├── event_bus.py          # Шина событий (PriorityQueue)
    │   ├── nfc_manager.py        # ★ NFC-мониторинг (NDEF/MIFARE/NTAG)
    │   ├── usb_diagnostics.py    # ★ USB-диагностика авторизованных устройств
    │   ├── bluetooth_scanner.py  # ★ BLE + Classic сканер, IoT-inventory
    │   ├── air_snitch.py         # ★ SDR/Sub-GHz сканер эфира (433/868 МГц)
    │   ├── wifi_sentinel.py      # ★ WiFi Sentinel + HoneyPot
    │   ├── smarthome_override.py # ★ Прямое Zigbee/Z-Wave/Tuya без облаков
    │   ├── power_sentry.py       # ★ Мониторинг UPS / энергосистемы
    │   └── android_service.py    # ArgosOmniService — unified background service
    │
    ├── factory/
    │   ├── replicator.py         # ZIP-репликация системы
    │   └── flasher.py            # IoT через COM-порты
    │
    ├── interface/
    │   ├── gui.py                # Desktop (CustomTkinter)
    │   ├── mobile_ui.py          # Android (Kivy + QuantumOrb)
    │   └── web_dashboard.py      # Браузер: localhost:8080
    │
    └── skills/
        ├── web_scrapper/         # DuckDuckGo (анонимный)
        ├── crypto_monitor/       # BTC/ETH + алерты
        ├── net_scanner/          # Сканер сети и портов
        ├── content_gen/          # AI-дайджест + Telegram
        ├── scheduler/            # Планировщик задач
        ├── evolution/            # Генерация навыков через ИИ
        ├── weather/              # Погода (пример навыка)
        └── smart_environments/   # Умные среды (расширенный)
```

---

## ⚡ Быстрый старт

### 1. Установка

```bash
# Всё сразу (включая PyAudio + SpeechRecognition)
python setup_builder.py --install

# Или вручную:
pip install -r requirements.txt
pip install PyAudio SpeechRecognition

# Опционально: расширенные модули (SDR/WiFi Sentinel/NFC/Watsonx/BLE)
pip install -r requirements-optional.txt
```

> **Windows — PyAudio не ставится:**
> ```bash
> pip install pipwin && pipwin install pyaudio
> ```
> **Linux:**
> ```bash
> sudo apt-get install portaudio19-dev && pip install PyAudio
> ```

### 2. .env

Аргос загружает `.env` через единый bootstrap: сначала из текущей рабочей директории, затем (если файл не найден) из корня репозитория. Это позволяет запускать `python main.py` как из корня проекта, так и из вложенных сценариев/обвязок.

```env
GEMINI_API_KEY=ключ_от_ai.google.dev
GIGACHAT_ACCESS_TOKEN=токен_gigachat_если_есть
# либо пара client credentials для авто-обновления токена:
# GIGACHAT_CLIENT_ID=...
# GIGACHAT_CLIENT_SECRET=...
YANDEX_IAM_TOKEN=iam_токен_yandex_cloud
YANDEX_FOLDER_ID=folder_id_yandex_cloud
# опционально: YANDEXGPT_MODEL_URI=gpt://<folder>/yandexgpt-lite/latest
TELEGRAM_BOT_TOKEN=токен_от_@BotFather
USER_ID=твой_telegram_id
ARGOS_NETWORK_SECRET=секрет_p2p
ARGOS_VOICE_DEFAULT=off  # off|on (по умолчанию Аргос молчит)
HA_URL=http://localhost:8123
HA_TOKEN=токен_home_assistant
HA_MQTT_HOST=localhost
HA_MQTT_PORT=1883
ARGOS_TASMOTA_DISCOVERY=on
ARGOS_TASMOTA_MQTT_HOST=localhost
ARGOS_TASMOTA_MQTT_PORT=1883
ARGOS_TASMOTA_DISCOVERY_TOPIC=homeassistant/#
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1/chat/completions
LMSTUDIO_MODEL=local-model
WATSONX_API_KEY=ключ_от_ibm_watsonx
WATSONX_PROJECT_ID=project_id_из_watsonx
WATSONX_URL=https://us-south.ml.cloud.ibm.com
ARGOS_HOMEOSTASIS=on
ARGOS_HOMEOSTASIS_INTERVAL=8
ARGOS_HOMEOSTASIS_PROTECT_CPU=78
ARGOS_HOMEOSTASIS_UNSTABLE_CPU=92
ARGOS_CURIOSITY=on
ARGOS_CURIOSITY_IDLE_SEC=600
ARGOS_CURIOSITY_RESEARCH_SEC=900
ARGOS_TASK_WORKERS=2
ARGOS_TASK_RETRIES=1
ARGOS_TASK_DEADLINE_SEC=120
ARGOS_TASK_BACKOFF_MS=500
ARGOS_TASK_RPS_SYSTEM=8
ARGOS_TASK_RPS_IOT=6
ARGOS_TASK_RPS_AI=3
ARGOS_TASK_RPS_HEAVY=1
ARGOS_P2P_FAILOVER_LIMIT=3
ARGOS_ALIGN_BATCH=8
ARGOS_DRAFTER_CALIBRATION=on
ARGOS_ACCEPTANCE_FLOOR=0.55
# опционально: тонкая настройка скоринга P2P
# ARGOS_P2P_WEIGHT_AUTH=0.5
# ARGOS_P2P_WEIGHT_POWER=0.5
# ARGOS_P2P_WEIGHT_QUEUE_PENALTY=2.5
# ARGOS_P2P_WEIGHT_INFLIGHT_PENALTY=1.5
# ARGOS_P2P_WEIGHT_RTT_PENALTY=0.04
# ARGOS_P2P_WEIGHT_ERROR_PENALTY=50
# ARGOS_P2P_WEIGHT_STALE_PENALTY=0.166
```

Примечание по Tasmota discovery:
- Аргос автоматически подписывается на `homeassistant/#` и регистрирует новые Tasmota-устройства.
- Метаданные устройств сохраняются в `data/argos.db` (таблица `iot_devices`) и в реестр IoT.
- Для Smart Flasher поддерживаются бинарники `assets/firmware/tasmota_relay.bin` и `assets/firmware/tasmota_sensor.bin` (если файлы присутствуют).

Примечание по лимитам:
- Для Gemini включён лимит: 15 запросов в минуту (включая Tool Calling и Vision).
- Лимит применяется только к Gemini; GigaChat, YandexGPT, LM Studio и Ollama не ограничиваются этим правилом.

Примечание по Auto-режиму:
- По умолчанию включён Auto-Consensus: модели отвечают по очереди с учётом предыдущих ответов, затем формируется единый итог.
- Управление через ENV: `ARGOS_AUTO_COLLAB=on|off`, `ARGOS_AUTO_COLLAB_MAX_MODELS=2..4`.

Примечание по SQLite (память):
- В текущей версии для `data/memory.db` включаются `WAL`, `busy_timeout=5000` и `synchronous=NORMAL`.
- Это снижает конкуренцию блокировок при высоком количестве параллельных операций записи.

### Production tuning presets

Ниже готовые профили для разных нагрузок. Выбирай один и копируй в `.env`.

#### Low load (1–2 ноды, домашний контур)
```env
ARGOS_TASK_WORKERS=2
ARGOS_TASK_RETRIES=1
ARGOS_TASK_DEADLINE_SEC=120
ARGOS_TASK_BACKOFF_MS=500
ARGOS_TASK_RPS_SYSTEM=8
ARGOS_TASK_RPS_IOT=6
ARGOS_TASK_RPS_AI=3
ARGOS_TASK_RPS_HEAVY=1
ARGOS_P2P_FAILOVER_LIMIT=2
```

#### Medium load (3–8 нод, смешанный IoT+AI)
```env
ARGOS_TASK_WORKERS=4
ARGOS_TASK_RETRIES=2
ARGOS_TASK_DEADLINE_SEC=180
ARGOS_TASK_BACKOFF_MS=600
ARGOS_TASK_RPS_SYSTEM=12
ARGOS_TASK_RPS_IOT=8
ARGOS_TASK_RPS_AI=5
ARGOS_TASK_RPS_HEAVY=2
ARGOS_P2P_FAILOVER_LIMIT=3
```

#### High load (9+ нод, тяжёлые пайплайны)
```env
ARGOS_TASK_WORKERS=8
ARGOS_TASK_RETRIES=3
ARGOS_TASK_DEADLINE_SEC=240
ARGOS_TASK_BACKOFF_MS=700
ARGOS_TASK_RPS_SYSTEM=16
ARGOS_TASK_RPS_IOT=12
ARGOS_TASK_RPS_AI=8
ARGOS_TASK_RPS_HEAVY=3
ARGOS_P2P_FAILOVER_LIMIT=4
```

Совет: при росте `error_rate` и `p95` в `p2p телеметрия` сначала уменьши `ARGOS_TASK_RPS_HEAVY` и `ARGOS_P2P_FAILOVER_LIMIT`, затем постепенно поднимай обратно.

### 3. Первый запуск

```bash
python genesis.py      # создаёт структуру папок
python main.py         # Desktop GUI + всё остальное
```

### 3.1 Проверка целостности (Health Check)

```bash
python health_check.py
```

Скрипт проверяет:
- наличие ключевых файлов и директорий,
- импорт основных модулей,
- валидность JSON-конфигов,
- целостность SQLite (`PRAGMA integrity_check`).

### 4. Интерактивная документация (MkDocs)

```bash
pip install -r docs/requirements-docs.txt
mkdocs serve
```

Открой: http://127.0.0.1:8000

Разделы документации:
- User Guide
- Developer Guide
- Philosophy (lore проекта)

---

## 🚀 Режимы запуска

```bash
python main.py                      # Desktop GUI
python main.py --no-gui             # Headless сервер
python main.py --mobile             # Android UI
python main.py --dashboard          # + Веб-панель :8080
python main.py --wake               # + Wake Word «Аргос»
python main.py --no-gui --dashboard # Сервер + панель
python main.py --root               # Запрос прав администратора
```

---

## 🧪 Примеры сценариев

В папке `examples/` лежат готовые шаблоны сценариев.

- `examples/scenarios/smart_home_monitor.json` — мониторинг умного дома, Vision-проверка и алерты.
- `examples/scenarios/security_incident_response.json` — реакция на security-инцидент: snapshot, диагностика, изоляция и rollback.
- `examples/scenarios/greenhouse_stability.json` — стабилизация климата теплицы с авто-регулировкой IoT-контуров.

Можно использовать как основу для своих DAG/планировщиков и автодействий.

---

## 🤝 Как помочь проекту

См. `CONTRIBUTING.md`:
- правила оформления PR,
- рекомендации по тестам и безопасности,
- направления, где особенно полезна помощь (skills, IoT, docs, observability).

### Web UI (FastAPI / Streamlit)

```bash
# FastAPI dashboard (используется автоматически в режиме --dashboard)
python main.py --dashboard

# Дополнительно: Streamlit админка поверх API FastAPI
streamlit run src/interface/streamlit_dashboard.py
```

---

## 🛰️ Протоколы, mesh и прошивка

Argos может работать как оператор сложных IoT-систем и систем жизнеобеспечения через шлюзы и сетевые мосты.

**Поддерживаемые протоколы:**
- BACnet (Building Automation and Control Networks)
- Modbus (RTU / ASCII / TCP)
- KNX
- LonWorks (Local Operating Network)
- M-Bus (Meter-Bus)
- OPC UA (Open Platform Communications Unified Architecture)
- MQTT

**Сети и радио:**
- Zigbee mesh
- LoRa mesh (включая SX1276)
- WiFi/гибридные mesh-топологии через gateway

**Прошивка и железо:**
- Прошивка контроллеров: STM32H503, ESP8266, RP2040
- Создание/конфигурация gateway и мостов для умных систем
- Управление умными устройствами прошивками для контроля систем жизнеобеспечения

**Типовые сценарии эксплуатации:**
- Умный дом
- Умная теплица
- Умный гараж
- Умный погреб
- Инкубатор
- Аквариум
- Террариум

---

## 💻 Сборка EXE и APK

```bash
# Windows exe с UAC
python build_exe.py
# → dist/argos.exe

# Установщик (нужен NSIS: nsis.sourceforge.io)
# Важно: для setup нужен режим --onedir (dist/argos)
python build_exe.py --onedir
python setup_builder.py --build
# → setup_argos.exe

# Android APK
pip install buildozer
# требуется buildozer.spec в корне проекта
buildozer android debug
# → bin/*.apk

# Telegram /apk использует внешнюю команду
# ARGOS_APK_BUILD_CMD="buildozer -v android debug"
```

---

## ⌨️ Все команды

### Мониторинг
```
статус системы    чек-ап    список процессов
алерты            установи порог cpu 85
геолокация        мой ip
```

### Файлы и терминал
```
файлы [путь]                    прочитай файл [путь]
создай файл [имя] [содержимое]  удали файл [путь]
консоль [команда]               убей процесс [имя]
```

### Vision (Gemini API)
```
посмотри на экран [вопрос]
что на экране
посмотри в камеру
анализ фото [путь/к/файлу.jpg]
```

### Агент (цепочки задач)
```
статус системы → затем крипто → потом отправь в telegram
1. сканируй сеть 2. запиши в файл devices.txt 3. дайджест
отчёт агента     останови агента
```

### Tool Calling (модель выбирает инструменты сама)
```
какая погода и сколько свободно места на диске?
покажи схемы инструментов
json схемы инструментов
```

### Память
```
запомни имя: Всеволод
запомни проект: Argos Universal OS
что ты знаешь
найди в памяти [запрос]
поиск по памяти [запрос]
граф знаний
забудь [ключ]
запиши заметку идея: здесь текст заметки
мои заметки
прочитай заметку 1
удали заметку 1
```

### Расписание
```
каждые 2 часа крипто
в 09:00 дайджест
через 30 мин статус системы
ежедневно в 08:30 чек-ап
расписание
удали задачу 1
```

### P2P Сеть
```
запусти p2p           статус сети
подключись к 192.168.1.10
синхронизируй навыки
распредели задачу [вопрос]
p2p телеметрия
p2p tuning
p2p вес [name] [value]
p2p failover [1..5]
p2p протокол          libp2p          zkp
```

### Загрузчик (требует подтверждения)
```
загрузчик
подтверди ARGOS-BOOT-CONFIRM
установи persistence
обнови grub
```

### Прочее
```
крипто          дайджест        опубликуй
сканируй сеть   список навыков  напиши навык [описание]
репликация      веб-панель
голос вкл/выкл  включи wake word
режим ии авто|gemini|gigachat|yandexgpt|lmstudio|ollama|watsonx
lmstudio статус
контекст диалога  сброс контекста
история         помощь
список модулей
гомеостаз статус | гомеостаз вкл | гомеостаз выкл
любопытство статус | любопытство вкл | любопытство выкл | любопытство сейчас
git статус | git коммит [сообщение] | git пуш | git автокоммит и пуш [сообщение]
очередь статус | очередь результаты | очередь метрики
в очередь [команда] [class=system|iot|ai|heavy priority=1..10 retries=N deadline=sec backoff=ms]
очередь воркеры [n]
```

### NFC
```
nfc статус                     # состояние NFC-подсистемы
nfc метки                      # зарегистрированные метки
nfc скан                       # сканировать одну метку
nfc регистрация [uid] [имя]    # зарегистрировать метку
nfc удали [uid]                # удалить метку
```

### USB-диагностика
```
usb статус                     # состояние USB-подсистемы
usb скан                       # сканировать подключённые устройства
usb авторизованные             # список авторизованных устройств
```

### Bluetooth
```
bt статус                      # состояние BT-подсистемы
bt инвентарь                   # полная инвентаризация устройств
bt скан                        # быстрый BLE-скан
bt iot                         # только IoT-устройства
```

### Home Assistant
```
ha статус
ha состояния
ha сервис light turn_on entity_id=light.kitchen brightness=180
ha mqtt home/livingroom/light/set state=ON brightness=180
```

### STT (локальный Faster-Whisper fallback)
```
# Аргос сначала пробует SpeechRecognition (google),
# при ошибке использует local faster-whisper.
```

---

## 📡 Telegram команды

```
/start     /status    /crypto    /history
/geo       /memory    /alerts    /network
/sync      /replicate /skills    /smart
/iot       /voice_on  /voice_off /help
```

---

## 🏠 Умные системы — Аргос как оператор

Аргос управляет 7 типами умных сред с автоматическими правилами:

| Тип | Сенсоры | Актуаторы |
|-----|---------|-----------|
| 🏠 **home** (дом) | temp, humidity, co2, motion, door, smoke | light, thermostat, lock, alarm, fan |
| 🌱 **greenhouse** (теплица) | temp, humidity, soil_moisture, light_lux, co2, ph | irrigation, heating, ventilation, lamp, shade |
| 🚗 **garage** (гараж) | gas, motion, door_open, temp, flood | gate, light, alarm, fan, heater |
| 🏚️ **cellar** (погреб) | temp, humidity, flood, co2 | fan, alarm, pump, heater |
| 🥚 **incubator** (инкубатор) | temp, humidity, co2, turn_count | heater, fan, turner, humidifier |
| 🐠 **aquarium** (аквариум) | temp, ph, tds, o2, water_level, ammonia | heater, pump, filter, lamp, co2_inject, feeder |
| 🦎 **terrarium** (террариум) | temp_hot, temp_cool, humidity, uvi, motion | lamp_uv, lamp_heat, mister, fan |

```
# Команды
создай умную систему                 # мастер: спросит тип, id, назначение, функции
отмена                              # отменить мастер создания
добавь систему greenhouse теплица_1
обнови сенсор теплица_1 temp 38
включи полив теплица_1
умные системы               # статус всех
добавь правило теплица_1 если soil_moisture < 25 то irrigation:on
```

Перед созданием через мастер Аргос задаёт вопросы:
- какой тип системы создать
- что она должна делать
- какие функции включить сразу

Каждый тип имеет встроенные автоматические правила (пожар → сирена, мороз → обогрев, и т.д.).

---

## 📡 IoT / Mesh-сеть

Аргос работает как центральный IoT-оператор:

| Протокол | Адаптер | Применение |
|----------|---------|------------|
| **Zigbee** | zigbee2mqtt (MQTT) | Датчики Xiaomi, Sonoff, Aqara |
| **LoRa** | UART AT-команды | Дальнобойные датчики (1-15 км) |
| **WiFi Mesh** | UDP broadcast | ESP-NOW, ESP32 |
| **MQTT** | paho-mqtt | Любые MQTT-устройства |
| **Modbus** | pymodbus | Промышленные контроллеры |

Фактическая матрица поддержки:

| Протокол/стек | Статус | Примечание |
|---------------|--------|------------|
| Zigbee (MQTT) | ✅ Implemented | Рабочий адаптер в IoTBridge |
| LoRa (UART AT) | ✅ Implemented | Рабочий адаптер в IoTBridge |
| WiFi Mesh (UDP) | ✅ Implemented | Рабочий mesh-адаптер |
| MQTT | ✅ Implemented | Общий MQTT bridge |
| Tasmota Discovery | ✅ Implemented | Zero-config через homeassistant/# |
| Modbus RTU/TCP | ✅ Implemented (minimal) | Runtime-адаптер в IoTBridge: serial/tcp + read/write holding registers |
| BACnet / KNX / LonWorks / M-Bus / OPC UA | 🧭 Planned/Template | Протоколы декларированы, отдельные runtime-адаптеры в IoTBridge пока не реализованы |

Поддерживаемые Zigbee-шлюзы (хабы экосистем):
- Aqara Hub M2
- Aqara Hub M1S Gen 2
- Xiaomi Mi Smart Home Hub (Multi-mode)
- Xiaomi Smart Home Hub 2
- Яндекс Станция Миди (со встроенным хабом)
- Яндекс Станция 2 (со встроенным хабом)
- Яндекс Станция Макс (с Zigbee)
- Tuya / Moes Multi-mode Gateway
- Digma Smart Zigbee Gateway
- Hubitat Elevation C-8

Поддерживаемые Zigbee-координаторы (стики/адаптеры):
- Sonoff Zigbee 3.0 USB Dongle Plus (ZBDongle-P)
- Sonoff Zigbee 3.0 USB Dongle Plus (ZBDongle-E)
- SMLIGHT SLZB-06 / 06M (Ethernet/PoE/USB)
- Home Assistant SkyConnect
- ConBee II / ConBee III
- ZigStar Stick v4
- JetHome USB Zigbee Stick
- Aeotec Zi-Stick
- Ugreen Zigbee USB Adapter
- CC2531 (устаревшая бюджетная модель)

```
# Команды
iot статус                    # список всех IoT-устройств
iot возможности               # фактическая матрица поддержки на текущей ноде
iot протоколы                 # полный список промышленных протоколов
статус устройства sensor_01   # детальный мониторинг устройства
подключи zigbee localhost     # подключить Zigbee через MQTT
подключи lora /dev/ttyUSB0    # подключить LoRa модем
подключи modbus /dev/ttyUSB0 9600      # Modbus RTU
подключи modbus tcp 192.168.1.10 502   # Modbus TCP
modbus чтение 100 2 1          # address=100, count=2, unit=1
modbus запись 120 55 1         # address=120, value=55, unit=1
запусти mesh                  # запустить UDP mesh
статус mesh                   # mesh-устройства
добавь устройство sensor_01 sensor zigbee addr_01 "Датчик кухня"
команда устройству sensor_01 temp 25
найди usb чипы                # авто-детект ESP32/RP2040/STM32 по USB
умная прошивка [/dev/ttyUSB0] # Smart Flasher (автовыбор + попытка заливки; показывает доступные firmware targets)
```

Zero-Config режим Tasmota:
- новые устройства подхватываются автоматически из Home Assistant Discovery-топиков,
- регистрация происходит без ручной команды добавления устройства.

---

## 🔧 IoT Шлюзы — создание и прошивка

Аргос генерирует конфиги и прошивает IoT-шлюзы:

| Шаблон | Описание |
|--------|----------|
| `esp32_zigbee` | ESP32 + CC2652 Zigbee координатор |
| `esp32_lora` | ESP32 + SX1276 LoRa шлюз |
| `rpi_mesh` | Raspberry Pi WiFi Mesh шлюз |
| `modbus_rtu` | USB-RS485 Modbus RTU |
| `lorawan_ttn` | LoRaWAN → The Things Network |

```
# Команды
шаблоны шлюзов                     # список шаблонов
создай прошивку gw_02 esp32_lora   # создать/обновить прошивку по шаблону
создай шлюз gw_01 esp32_zigbee     # создать конфиг
прошей шлюз gw_01 /dev/ttyUSB0     # прошить/деплой
список шлюзов                       # все созданные
конфиг шлюза gw_01                  # посмотреть JSON
прошей gateway /dev/ttyUSB0 zigbee_gateway  # прошить напрямую
```

---

## ⚛️ Квантовые состояния

| Состояние | Цвет | Режим |
|-----------|------|-------|
| Analytic | 🔵 Cyan | Холодный анализ |
| Creative | 🟣 Purple | Творческий синтез |
| Protective | 🔴 Red | Защитный протокол |
| Unstable | 🟡 Yellow | Аномалия обнаружена |
| All-Seeing | 🟢 Green | Полное наблюдение |

---

## 🌐 P2P — принцип

```
Нода A (30 дней, 72/100)   Нода B (90 дней, 88/100)👑   Нода C (1 день, 25/100)
Авторитет: 102             Авторитет: 145 МАСТЕР         Авторитет: 18
```
**Авторитет = мощность × log(возраст + 2)**

- UDP broadcast — автообнаружение в локальной сети
- TCP + HMAC — защищённый обмен навыками
- Heavy-задачи (Vision/compile/firmware) маршрутизируются на server/worker-ноды,
  чтобы не перегружать слабые gateway-узлы
- При росте CPU-тренда локально включается preemptive failover: heavy-задачи сбрасываются
  на соседние ноды до перехода CPU в состояние `Unstable`
- Adaptive routing: при выборе ноды учитываются live-метрики (RTT, inflight, p95 latency,
  error_rate, свежесть состояния), есть failover на топ-кандидатов и локальный fallback
- Live-тюнинг роутинга доступен командами `p2p tuning`, `p2p вес [name] [value]`, `p2p failover [1..5]`
- **Speculative Consensus v2**: несколько Drafter-нод генерируют ответы параллельно, Verifier-нода
  агрегирует с аннотацией `[ERRORS]` / `[FINAL]`, per-drafter quality tracking через observability
- **Role Routing**: роль назначается автоматически — gateway/weak (≤2 cores, <3 GB RAM) → Drafter,
  master/мощная нода → Verifier; формула: `max(authority, ram_score)`
- **Acceptance Rate**: per-drafter метрики приёмки (`observability.get_drafter_acceptance()`),
  `drafter_quality_report()` с trend-анализом; при падении acceptance ниже floor — backpressure RPS,
  при отскоке +10% — auto-recovery RPS обратно к baseline
- **Batch Idle Learning**: в idle-цикле до 8 уроков за пакет (`ARGOS_ALIGN_BATCH`), Active Drafter
  Calibration — few-shot зондирование drafter-а по exemplar-у verifier-а

Roadmap:
- Migration target: libp2p (Kademlia/mDNS + gossipsub + request-response)
- Privacy roadmap: ZKP (selective disclosure → proof-of-attribute → proof-of-policy)

---

## 🤖 Агентный режим

```
"сканируй сеть → найди новые устройства → запиши в devices.txt → отправь в Telegram"
```
Аргос разбивает задачу на шаги, выполняет последовательно, отчитывается.

---

## 🧬 Саморазвитие

```
аргос, напиши навык для мониторинга погоды
  → Gemini генерирует Python-код
  → ast.parse() проверяет синтаксис
  → сохраняет в src/skills/weather.py
  → навык немедленно доступен
  → синхронизируется со всей P2P-сетью
```

---

## 📊 Аудит v1.0.0-Absolute

```
83 файла Python · 83/83 синтаксис ✅
30/30 функциональных тестов ✅
50+ импортируемых модулей
130+ голосовых/текстовых команд
7 умных систем · 5 IoT-протоколов · 5 шаблонов шлюзов
NFC / USB / Bluetooth подсистемы
AWA-Core · Adaptive Drafter · Self-Healing · AirSnitch · WiFi Sentinel
SmartHome Override · Power Sentry · Emergency Purge · Container Isolation
Master Auth · Biosphere DAG · IBM Quantum Bridge
Speculative Consensus v2 · Batch Idle Learning · P2P Role Routing
~14100 строк кода
```

---

## 🐳 Docker

```bash
docker-compose up -d
# Headless + Telegram + P2P + Dashboard :8080
```

---

## ⚖️ Лицензия

Apache License 2.0 — Всеволод / Argos Project, 2026

---

*"Аргос не спит. Аргос видит. Аргос помнит."* 👁️
