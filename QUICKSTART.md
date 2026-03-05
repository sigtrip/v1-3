# 🚀 ARGOS Quick Start Guide

Быстрое руководство по запуску ARGOS Universal OS за 5 минут.

---

## 📋 Предварительные требования

- **Python 3.11+**
- **Git**
- **OpenSSL** (для генерации секретов)

**Для Android:**
- Buildozer
- Android SDK/NDK

---

## ⚡ Быстрый старт (5 минут)

### Шаг 1: Клонирование репозитория

```bash
git clone https://github.com/sigtrip/v1-3.git
cd v1-3
```

### Шаг 2: Установка зависимостей

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Шаг 3: Настройка окружения

**Автоматический способ (рекомендуется):**
```bash
# Автоматическая генерация секретов
python setup_secrets.py --auto

# Или интерактивный режим с вводом API ключей
python setup_secrets.py
```

**Ручной способ:**
```bash
# Скопировать шаблон конфигурации
cp .env.example .env

# Сгенерировать уникальные секреты
echo "Генерация ARGOS_NETWORK_SECRET..."
openssl rand -hex 32

echo "Генерация ARGOS_MASTER_KEY..."
openssl rand -hex 32
```

**Откройте `.env` и добавьте:**
```env
GEMINI_API_KEY=ваш_ключ_от_ai.google.dev
TELEGRAM_BOT_TOKEN=ваш_токен_от_@BotFather
USER_ID=ваш_telegram_id
ARGOS_NETWORK_SECRET=<результат_первой_команды>
ARGOS_MASTER_KEY=<результат_второй_команды>
```

**Проверка конфигурации:**
```bash
python setup_secrets.py --check
```

### Шаг 4: Инициализация

```bash
python genesis.py
```

Эта команда создаст:
- `config/` - конфигурационные файлы
- `data/` - базы данных
- `logs/` - логи
- `builds/` - артефакты сборки

### Шаг 5: Запуск

**Desktop GUI:**
```bash
python main.py
```

**Headless (без GUI):**
```bash
python main.py --no-gui
```

**С веб-панелью:**
```bash
python main.py --dashboard
# Откройте http://localhost:8080
```

---

## 🔑 Получение API ключей

### Gemini API Key

1. Перейдите на https://ai.google.dev/
2. Нажмите "Get API Key"
3. Создайте новый проект или выберите существующий
4. Скопируйте ключ в `.env` → `GEMINI_API_KEY`

### Telegram Bot Token

1. Откройте Telegram, найдите @BotFather
2. Отправьте `/newbot`
3. Следуйте инструкциям (имя, username)
4. Скопируйте токен в `.env` → `TELEGRAM_BOT_TOKEN`

### Ваш Telegram ID

1. Откройте Telegram, найдите @userinfobot
2. Отправьте `/start`
3. Скопируйте ваш ID в `.env` → `USER_ID`

---

## 🐳 Запуск через Docker

```bash
# Сборка образа
docker build -t argos:latest .

# Запуск контейнера
docker run -d \
  --name argos \
  --env-file .env \
  -p 8080:8080 \
  -p 55771:55771 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  argos:latest

# Проверка логов
docker logs -f argos
```

**Или используйте Docker Compose:**

```bash
docker-compose up -d
```

---

## 📱 Сборка Android APK

### Установка Buildozer (Linux/macOS)

```bash
pip install buildozer

# Установка системных зависимостей (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y \
  git zip unzip openjdk-17-jdk \
  autoconf libtool pkg-config \
  zlib1g-dev libncurses5-dev \
  libncursesw5-dev libtinfo5 \
  cmake libffi-dev libssl-dev
```

### Сборка APK

```bash
# Debug версия (для тестирования)
buildozer android debug

# Release версия (для production)
buildozer android release

# APK будет в папке bin/
ls -lh bin/*.apk
```

### Установка на Android

**Через USB (ADB):**
```bash
adb install bin/argos-1.3-arm64-v8a-debug.apk
```

**Через файловый менеджер:**
1. Скопируйте APK на устройство
2. Откройте файловый менеджер
3. Нажмите на APK → Установить
4. Разрешите установку из неизвестных источников

---

## ✅ Проверка установки

```bash
# Проверка целостности
python health_check.py

# Проверка зависимостей
pip list | grep -E "kivy|cryptography|requests"

# Проверка конфигурации
cat config/identity.json
```

**Ожидаемый вывод health_check.py:**
```
✅ Все модули импортируются корректно
✅ Конфигурационные файлы валидны
✅ База данных в порядке
✅ Система готова к работе
```

---

## 🎯 Первые команды

После запуска попробуйте:

```
статус системы
помощь
что ты знаешь
режим ии gemini
привет, аргос
```

**Через Telegram бота:**
```
/start
/status
/help
```

---

## 🔧 Решение проблем

### Ошибка: "ModuleNotFoundError: No module named 'kivy'"

```bash
pip install kivy>=2.3.0
```

### Ошибка: "GEMINI_API_KEY not found"

Проверьте `.env`:
```bash
cat .env | grep GEMINI_API_KEY
```

Если пусто, добавьте ключ.

### Ошибка: "Permission denied" при запуске

**Linux/macOS:**
```bash
chmod +x main.py
python main.py
```

### Buildozer ошибка: "libtinfo5 not found"

**Ubuntu 22.04+:**
```bash
sudo apt-get install libtinfo5
```

### Docker ошибка: "Cannot connect to Docker daemon"

```bash
# Запустите Docker daemon
sudo systemctl start docker

# Добавьте пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker
```

---

## 📚 Дополнительная документация

- **Полная документация:** [README.md](./README.md)
- **Политика безопасности:** [SECURITY.md](./SECURITY.md)
- **Отчет об исправлениях:** [AUDIT_FIXES_SUMMARY.md](./AUDIT_FIXES_SUMMARY.md)
- **Changelog:** [CHANGELOG.md](./CHANGELOG.md)
- **Contributing:** [CONTRIBUTING.md](./CONTRIBUTING.md)

---

## 🆘 Помощь

**Проблемы:**
- GitHub Issues: https://github.com/sigtrip/v1-3/issues

**Security:**
- Email: seva1691@mail.ru
- См. [SECURITY.md](./SECURITY.md)

**Общие вопросы:**
- Telegram: (укажите канал/группу)
- Email: seva1691@mail.ru

---

## 🎉 Готово!

Теперь ARGOS запущен и готов к работе. Попробуйте базовые команды и изучите полную документацию в [README.md](./README.md).

**Следующие шаги:**
1. Изучите команды: `помощь`
2. Настройте P2P сеть: `запусти p2p`
3. Подключите IoT устройства: `iot статус`
4. Создайте умную систему: `создай умную систему`

---

**Версия:** 1.3  
**Последнее обновление:** 5 марта 2026
