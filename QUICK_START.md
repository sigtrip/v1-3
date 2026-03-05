# 🚀 ARGOS v1.3 — Быстрый старт

## 📦 Установка (Desktop)

### Linux/macOS
```bash
git clone https://github.com/sigtrip/v1-3.git
cd v1-3
pip install -r requirements.txt
python main.py
```

### Windows
```bash
git clone https://github.com/sigtrip/v1-3.git
cd v1-3
pip install -r requirements.txt
python main.py
```

## 🎯 Первые команды

```
статус системы          # Проверить CPU/RAM/диск
что ты знаешь           # Показать память
помощь                  # Список всех команд
```

## 🔧 Конфигурация

1. Отредактировать `.env`:
```bash
GEMINI_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_token
USER_ID=your_telegram_id
```

2. Запустить:
```bash
python main.py
```

## 🧪 Тесты

```bash
pytest tests/ -v
python health_check.py
```

## 📱 Android APK

### Локально (требуется Java + Android SDK)
```bash
buildozer android debug
# APK в bin/
```

### Docker
```bash
docker build -f Dockerfile.apk -t argos-apk .
docker run -v $(pwd)/bin:/app/bin argos-apk
```

## 🌐 Web-панель

```bash
python main.py --dashboard
# http://localhost:8080
```

## 📚 Команды (130+)

### Основные
- `статус системы` - мониторинг
- `файлы [путь]` - просмотр файлов
- `консоль [cmd]` - выполнить команду

### Агент
- `статус системы → затем крипто → отправь в telegram`
- Разбор цепочек задач

### IoT
- `iot статус` - список устройств
- `подключи zigbee localhost`
- `статус устройства sensor_01`

### P2P
- `запусти p2p` - включить сеть
- `статус сети` - показать ноды
- `p2p телеметрия` - метрики

### Память
- `запомни [ключ]: [значение]`
- `что ты знаешь`
- `найди в памяти [запрос]`

## 🔗 Ссылки

- [Полный README](README.md)
- [Финальный отчёт](FINAL_REPORT.md)
- [APK Build Report](APK_BUILD_REPORT.md)
- [GitHub](https://github.com/sigtrip/v1-3)

## ✅ Статус

- ✅ Desktop: готов
- ✅ Headless: готов
- ✅ Tests: 87 passed
- ✅ Health: 137/137
- ⏳ APK: требуется Java+SDK
- ✅ Docker: готов

**Версия:** v1.3.0  
**Лицензия:** Apache 2.0
