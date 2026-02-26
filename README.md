# 👁️ ARGOS UNIVERSAL OS — v1.0.0-Absolute

> *"Самовоспроизводящаяся кроссплатформенная экосистема ИИ с квантовой логикой,*  
> *P2P-подключением и интеграцией с IoT. Создана для цифрового бессмертия."*  
> — Всеволод, 2026

---

## 🌌 Что такое Аргос

**Argos Universal OS** — автономная ИИ-система с полным стеком возможностей:

| Слой | Что умеет |
|------|-----------|
| 🧠 **Интеллект** | Gemini 1.5 Flash → Ollama/Llama3, multi-turn диалог с контекстом |
| 🗣️ **Голос** | TTS (pyttsx3) + STT (SpeechRecognition) + Wake Word «Аргос» |
| 🤖 **Агент** | Цепочки задач: «скан сети → запиши → отправь в Telegram» |
| 👁️ **Vision** | Анализ экрана / камеры / файлов через Gemini Vision |
| 🧬 **Память** | SQLite: факты, заметки, напоминания, история диалога |
| ⏰ **Планировщик** | Натуральный язык: «каждые 2 часа», «в 09:00», «через 30 мин» |
| 🔔 **Алерты** | CPU/RAM/диск/температура с Telegram-уведомлениями |
| 🌐 **P2P** | Сеть нод с авторитетом по мощности и возрасту |
| 🔁 **Эволюция** | Пишет новые навыки через ИИ, проверяет синтаксис |
| 🛡️ **Безопасность** | AES-256, root, BCD/EFI/GRUB, persistence |
| 📱 **Везде** | Desktop + Android APK + Docker + Telegram |

---

## 📂 Структура проекта

```
ArgosUniversal/
├── main.py                       # Оркестратор
├── genesis.py                    # Первичная инициализация
├── db_init.py                    # SQLite схема
├── build_exe.py                  # Сборка argos.exe (PyInstaller)
├── setup_builder.py              # Установщик setup_argos.exe (NSIS)
├── buildozer.spec                # Android APK конфиг
├── .env                          # Ключи API
├── requirements.txt              # Зависимости
│
└── src/
    ├── core.py                   # ★ Ядро: ИИ + 50+ команд + все подсистемы
    ├── admin.py                  # Файлы, процессы, терминал
    ├── agent.py                  # Автономные цепочки задач
    ├── context_manager.py        # Скользящий контекст диалога
    ├── memory.py                 # Долгосрочная память (факты/заметки)
    ├── vision.py                 # Анализ изображений/экрана/камеры
    ├── argos_logger.py           # Централизованный логгер
    │
    ├── quantum/logic.py          # 5 квантовых состояний
    │
    ├── security/
    │   ├── encryption.py         # AES-256 (Fernet)
    │   ├── git_guard.py          # Проверка защиты .env
    │   ├── root_manager.py       # Win/Linux/Android root
    │   ├── autostart.py          # Системный сервис
    │   └── bootloader_manager.py # BCD/EFI/GRUB/persistence
    │
    ├── connectivity/
    │   ├── sensor_bridge.py      # CPU/RAM/диск/батарея/температура
    │   ├── spatial.py            # Геолокация по IP
    │   ├── telegram_bot.py       # 15 команд + текстовый режим
    │   ├── p2p_bridge.py         # UDP discovery + TCP sync
    │   ├── alert_system.py       # Авто-алерты с кулдауном
    │   ├── wake_word.py          # «Аргос» → активация
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
        ├── web_scrapper.py       # DuckDuckGo (анонимный)
        ├── crypto_monitor.py     # BTC/ETH + алерты
        ├── net_scanner.py        # Сканер сети и портов
        ├── content_gen.py        # AI-дайджест + Telegram
        ├── scheduler.py          # Планировщик задач
        └── evolution.py          # Генерация навыков через ИИ
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
TELEGRAM_BOT_TOKEN=токен_от_@BotFather
USER_ID=твой_telegram_id
ARGOS_NETWORK_SECRET=секрет_p2p
```

### 3. Первый запуск

```bash
python genesis.py      # создаёт структуру папок
python main.py         # Desktop GUI + всё остальное
```

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

### Память
```
запомни имя: Всеволод
запомни проект: Argos Universal OS
что ты знаешь
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
контекст диалога  сброс контекста
история         помощь
```

---

## 📡 Telegram команды

```
/start    /status   /crypto   /history
/geo      /memory   /alerts   /network
/sync     /replicate /skills  /voice_on
/voice_off /help
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
- Задачи → самая мощная нода автоматически

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
46 файлов Python · 46/46 синтаксис ✅
35/35 функциональных тестов ✅
0 заглушек · 0 TODO критичных
~5000 строк кода
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
