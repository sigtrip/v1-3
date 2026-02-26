# Argos Universal OS - Quick Reference Guide

## 🚀 Quick Start

```bash
# 1. Initialize the system
python genesis.py

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run Argos
python main.py
```

## 📝 Common Commands

### System Monitoring
- `статус системы` - System status (CPU, RAM, OS info)
- `процессы` - List running processes
- `аномалии` - Scan for system anomalies
- `файлы [path]` - List directory contents

### Security
- `аудит безопасности` - Security audit of config directory
- `проверка щита` - Check Shield Protocol status

### Quantum Operations
- `квантовое состояние` - Current quantum state
- `вектор вероятности` - Quantum probability vector

### Network
- `поиск [query]` - Web search via DuckDuckGo
- `новости` - Get tech news
- `проверка сети` - Check network connectivity

### System Management
- `консоль [command]` - Execute system command
- `убей процесс [name]` - Kill process by name
- `репликация` - Create system archive
- `резервная копия` - Backup critical files

### IoT & Factory
- `сканируй порты` - Scan for connected devices

### Information
- `помощь` - Show all commands
- `личность` - Show Argos identity

## 🛡️ Protocol "Нулевой Пациент"

Activate all protocols with:
```bash
python main.py 'протокол "нулевой пациент"'
```

This will:
1. Check quantum core status
2. Audit security (config directory)
3. Scan for process anomalies
4. Test network connectivity

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## 📂 Directory Structure

```
ArgosUniversal/
├── main.py              # Main orchestrator
├── genesis.py           # System initialization
├── config/              # Configuration files
│   └── identity.json    # Argos identity
├── src/                 # Source modules
│   ├── core.py         # Command dispatcher
│   ├── admin.py        # System administration
│   ├── quantum/        # Quantum logic
│   ├── security/       # Encryption & security
│   ├── skills/         # Web scraping
│   ├── factory/        # IoT & replication
│   └── connectivity/   # Telegram bridge
├── logs/               # System logs
├── backups/            # System backups
└── archives/           # System archives
```

## 🔧 Environment Variables

Create `.env` file from `.env.example`:

```bash
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GEMINI_API_KEY=your_key_here
```

## 📊 Module Overview

| Module | Purpose |
|--------|---------|
| `quantum/logic.py` | 5-state quantum decision engine |
| `security/encryption.py` | AES-256 Shield Protocol + GitGuard |
| `admin.py` | Deep system administration |
| `skills/web_scrapper.py` | Argos Eyes network monitoring |
| `evolution.py` | Self-modification & backup |
| `factory/flasher.py` | IoT device scanning |
| `factory/replicator.py` | System replication |
| `connectivity/telegram.py` | Remote Telegram control |

## 🎯 Key Features

- ⚛️ **Quantum Logic**: 5-state probability system
- 🛡️ **Shield Protocol**: AES-256 encryption
- 🧠 **Deep Admin**: Full system control
- 📡 **Argos Eyes**: Web monitoring
- 🔄 **Evolution**: Self-modification
- 🏭 **Factory**: IoT integration
- 📱 **Remote Bridge**: Telegram control

## ⚖️ License

Apache License 2.0 - See LICENSE file for details.

**Creator**: Всеволод
**Version**: 1.0.0-Absolute
**Year**: 2026
