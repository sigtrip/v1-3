# User Guide: Запуск и установка

## 1) Установка зависимостей

```bash
pip install -r requirements.txt
```

Для голосовых функций также могут понадобиться системные пакеты (например, PortAudio).

## 2) Настройка окружения

Создай `.env` в корне проекта и укажи минимально необходимые ключи:

```env
GEMINI_API_KEY=...
ARGOS_NETWORK_SECRET=...
```

Загрузка `.env` выполняется через bootstrap с fallback: сначала из текущей рабочей директории запуска, затем из корня репозитория.

Если используешь Telegram и Home Assistant — добавь соответствующие переменные из README.

## 3) Инициализация и запуск

```bash
python genesis.py
python main.py
```

Режимы запуска:

- Desktop: `python main.py`
- Headless: `python main.py --no-gui`
- Dashboard: `python main.py --dashboard`

## 4) Первые команды

- `статус системы`
- `что ты знаешь`
- `найди в памяти кот`
- `граф знаний`
- `запусти p2p`
