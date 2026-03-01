# 👁️ ARGOS UNIVERSAL OS — v1.0.0-Absolute

> *"Самовоспроизводящаяся кроссплатформенная экосистема ИИ с квантовой логикой,*  
> *P2P-подключением и интеграцией с IoT. Создана для цифрового бессмертия."*  
> — Всеволод, 2026

---

## 🌌 Что такое Аргос

**Argos Universal OS** — автономная ИИ-система с полным стеком возможностей:

| Слой | Что умеет |
|------|-----------|
| 🧠 **Интеллект** | Gemini / GigaChat / YandexGPT / LM Studio → Ollama/Llama3, multi-turn + Tool Calling по JSON-схемам |
| 🗣️ **Голос** | TTS (pyttsx3) + STT (SpeechRecognition) + Wake Word «Аргос» |
| 🤖 **Агент** | Цепочки задач: «скан сети → запиши → отправь в Telegram» |
| 👁️ **Vision** | Анализ экрана / камеры / файлов через Gemini Vision |
| 🧬 **Память** | SQLite: факты, заметки, напоминания, история диалога |
| ⏰ **Планировщик** | Натуральный язык: «каждые 2 часа», «в 09:00», «через 30 мин» |
| 🔔 **Алерты** | CPU/RAM/диск/температура с Telegram-уведомлениями |
| ⚛️ **Гомеостаз железа** | Автомониторинг CPU/RAM/TEMP, защитные состояния Protective/Unstable, троттлинг тяжёлых задач |
| 🌐 **P2P** | Сеть нод с авторитетом по мощности и возрасту |
| 🧭 **Автономное любопытство** | В idle-режиме исследует факты из памяти, тянет свежую сеть и пишет инсайты в SQLite |
| 🔁 **Эволюция** | Жёсткий code-gate: только валидный исполняемый Python-код + review + unit-тест |
| 🛡️ **Безопасность** | AES-256-GCM, root, BCD/EFI/GRUB, persistence |
| 📱 **Везде** | Desktop + Android APK + Docker + Telegram |
| 🏠 **Умные системы** | Дом, теплица, гараж, погреб, инкубатор, аквариум, террариум |
| 📡 **IoT / Mesh** | Zigbee, LoRa, WiFi Mesh, MQTT, Modbus — оператор mesh-сетей и шлюзов |
| 🏭 **Пром. протоколы** | BACnet, Modbus RTU/ASCII/TCP, KNX, LonWorks, M-Bus, OPC UA, MQTT |
| 🔧 **Шлюзы/прошивка** | Создание gateway, прошивка ESP8266/RP2040/STM32H503, поддержка LoRa SX1276 |
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
    ├── hardware_guard.py         # Квантовый гомеостаз железа
    ├── git_ops.py                # Безопасные Git status/commit/push
    ├── evolution.py              # Эволюция (базовый)
    ├── icon_generator.py         # Генератор иконок
    │
    ├── quantum/logic.py          # 5 квантовых состояний
    │
    ├── security/
    │   ├── encryption.py         # AES-256-GCM (cryptography)
    │   ├── git_guard.py          # Защита .env/.gitignore
    │   ├── root_manager.py       # Win/Linux/Android root
    │   ├── autostart.py          # Системный сервис
    │   └── bootloader_manager.py # BCD/EFI/GRUB/persistence
    │
    ├── connectivity/
    │   ├── sensor_bridge.py      # CPU/RAM/диск/батарея/температура
    │   ├── spatial.py            # Геолокация по IP
    │   ├── telegram_bot.py       # 16 команд + текстовый режим
    │   ├── p2p_bridge.py         # UDP discovery + TCP sync
    │   ├── alert_system.py       # Авто-алерты с кулдауном
    │   ├── wake_word.py          # «Аргос» → активация
    │   ├── iot_bridge.py         # ★ IoT-мост: Zigbee/LoRa/Mesh/MQTT
    │   ├── mesh_network.py       # ★ Mesh-сеть + прошивка gateway
    │   ├── gateway_manager.py    # ★ Создание и прошивка IoT-шлюзов
    │   ├── event_bus.py          # Шина событий (PriorityQueue)
    │   └── android_service.py    # Фоновый сервис Android
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
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1/chat/completions
LMSTUDIO_MODEL=local-model
ARGOS_HOMEOSTASIS=on
ARGOS_HOMEOSTASIS_INTERVAL=8
ARGOS_HOMEOSTASIS_PROTECT_CPU=78
ARGOS_HOMEOSTASIS_UNSTABLE_CPU=92
ARGOS_CURIOSITY=on
ARGOS_CURIOSITY_IDLE_SEC=600
ARGOS_CURIOSITY_RESEARCH_SEC=900
```

Примечание по лимитам:
- Для Gemini включён лимит: 15 запросов в минуту (включая Tool Calling и Vision).
- Лимит применяется только к Gemini; GigaChat, YandexGPT, LM Studio и Ollama не ограничиваются этим правилом.

Примечание по Auto-режиму:
- По умолчанию включён Auto-Consensus: модели отвечают по очереди с учётом предыдущих ответов, затем формируется единый итог.
- Управление через ENV: `ARGOS_AUTO_COLLAB=on|off`, `ARGOS_AUTO_COLLAB_MAX_MODELS=2..4`.

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
python build_exe.py --onedir
python setup_builder.py --build
# → setup_argos.exe

# Android APK
pip install buildozer
buildozer android debug
# → bin/*.apk
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
режим ии авто|gemini|gigachat|yandexgpt|lmstudio|ollama
контекст диалога  сброс контекста
история         помощь
список модулей
гомеостаз статус | гомеостаз вкл | гомеостаз выкл
любопытство статус | любопытство вкл | любопытство выкл | любопытство сейчас
git статус | git коммит [сообщение] | git пуш | git автокоммит и пуш [сообщение]
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

```
# Команды
iot статус                    # список всех IoT-устройств
iot протоколы                 # полный список промышленных протоколов
статус устройства sensor_01   # детальный мониторинг устройства
подключи zigbee localhost     # подключить Zigbee через MQTT
подключи lora /dev/ttyUSB0    # подключить LoRa модем
запусти mesh                  # запустить UDP mesh
статус mesh                   # mesh-устройства
добавь устройство sensor_01 sensor zigbee addr_01 "Датчик кухня"
команда устройству sensor_01 temp 25
найди usb чипы                # авто-детект ESP32/RP2040/STM32 по USB
умная прошивка [/dev/ttyUSB0] # Smart Flasher (автовыбор + попытка заливки)
```

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
68 файлов Python · 68/68 синтаксис ✅
30/30 функциональных тестов ✅
40+ импортируемых модулей
80+ голосовых/текстовых команд
7 умных систем · 5 IoT-протоколов · 5 шаблонов шлюзов
~7000 строк кода
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
