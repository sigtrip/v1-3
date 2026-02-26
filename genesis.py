#!/usr/bin/env python3
"""
Genesis - Первичная инициализация системы Argos.
Создает необходимые директории и конфигурационные файлы.
"""

import os
import json
from pathlib import Path
from datetime import datetime


def create_directory_structure():
    """Создание структуры директорий."""
    directories = [
        'config',
        'src/quantum',
        'src/security',
        'src/factory',
        'src/skills',
        'src/connectivity',
        'logs',
        'backups',
        'archives'
    ]
    
    print("📁 Создание структуры директорий...")
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {directory}")


def create_identity_file():
    """Создание файла личности Argos."""
    identity = {
        "name": "Argos",
        "version": "1.0.0-Absolute",
        "creator": "Всеволод",
        "build_year": 2026,
        "status": "ONLINE",
        "description": "Аргос — всевидящий, всезнающий, неизменный.",
        "personality": {
            "core_traits": [
                "всевидящий",
                "всезнающий",
                "неизменный"
            ],
            "mode": "guardian",
            "language": "ru"
        },
        "capabilities": [
            "Deep Admin",
            "Quantum Logic",
            "Argos Eyes",
            "Shield Protocol",
            "Remote Bridge"
        ],
        "protocols": {
            "security": "AES-256",
            "quantum_states": 5,
            "ai_fallback": "local"
        },
        "initialized": datetime.now().isoformat()
    }
    
    config_path = Path('config/identity.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(identity, f, ensure_ascii=False, indent=2)
    
    print(f"\n🆔 Файл личности создан: {config_path}")


def create_env_template():
    """Создание шаблона .env файла."""
    env_template = """# Argos Universal OS - Environment Variables

# Telegram Configuration (опционально)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Google Gemini API (опционально)
GEMINI_API_KEY=your_gemini_api_key_here

# Ollama Configuration (опционально)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3

# Security
ENCRYPTION_KEY_PATH=config/encryption.key
"""
    
    env_path = Path('.env.example')
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_template)
    
    print(f"📝 Шаблон .env создан: {env_path}")


def create_gitignore():
    """Создание .gitignore файла."""
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
.venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Logs
logs/
*.log

# Backups & Archives
backups/
archives/

# Environment variables
.env

# Security
config/encryption.key
*.key
*.pem

# OS
.DS_Store
Thumbs.db
"""
    
    gitignore_path = Path('.gitignore')
    with open(gitignore_path, 'w', encoding='utf-8') as f:
        f.write(gitignore_content)
    
    print(f"🔒 .gitignore создан: {gitignore_path}")


def print_welcome_message():
    """Вывод приветственного сообщения."""
    message = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║              🎉 ARGOS ИНИЦИАЛИЗИРОВАН 🎉                  ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    
    ✅ Структура директорий создана
    ✅ Файл личности настроен
    ✅ Шаблоны конфигурации готовы
    
    📋 Следующие шаги:
    
    1. Установите зависимости:
       pip install -r requirements.txt
    
    2. (Опционально) Настройте .env файл:
       cp .env.example .env
       nano .env
    
    3. Запустите Argos:
       python main.py
    
    4. Или выполните протокол "Нулевой Пациент":
       python main.py протокол "нулевой пациент"
    
    🛡️  Система Argos готова к работе!
    """
    print(message)


def main():
    """Главная функция инициализации."""
    print("\n🌟 Начало инициализации Argos Universal OS...\n")
    
    # Создание структуры
    create_directory_structure()
    
    # Создание конфигурационных файлов
    create_identity_file()
    create_env_template()
    create_gitignore()
    
    # Финальное сообщение
    print_welcome_message()


if __name__ == '__main__':
    main()
