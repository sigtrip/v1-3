#!/usr/bin/env python3
"""
check_readiness.py - Проверка готовности ARGOS к запуску

Проверяет:
- Установку Python и версию
- Наличие всех зависимостей
- Конфигурацию .env
- Структуру директорий
- Доступность портов
- Права доступа к файлам

Использование:
    python check_readiness.py              # Полная проверка
    python check_readiness.py --quick      # Быстрая проверка
    python check_readiness.py --fix        # Попытка автоисправления
"""

import sys
import os
import socket
from pathlib import Path
import importlib.util


class ReadinessChecker:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []

    def check_python_version(self):
        """Проверка версии Python."""
        print("🐍 Проверка Python...")
        version = sys.version_info
        if version.major == 3 and version.minor >= 10:
            print(f"  ✅ Python {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            self.errors.append(f"Python {version.major}.{version.minor} < 3.10")
            print(f"  ❌ Python {version.major}.{version.minor} (требуется >= 3.10)")
            return False

    def check_dependencies(self):
        """Проверка установки зависимостей."""
        print("\n📦 Проверка зависимостей...")

        required = [
            "requests",
            "cryptography",
            "psutil",
            "paho.mqtt",
        ]

        optional = [
            "kivy",
            "google.genai",
            "telegram",
            "fastapi",
            "uvicorn",
        ]

        all_ok = True

        for module in required:
            if self._check_module(module):
                print(f"  ✅ {module}")
            else:
                print(f"  ❌ {module} (обязательный)")
                self.errors.append(f"Модуль {module} не установлен")
                all_ok = False

        for module in optional:
            if self._check_module(module):
                print(f"  ✅ {module}")
            else:
                print(f"  ⚠️  {module} (опциональный)")
                self.warnings.append(f"Модуль {module} не установлен")

        return all_ok

    def _check_module(self, module_name):
        """Проверяет установку модуля."""
        spec = importlib.util.find_spec(module_name)
        return spec is not None

    def check_env_file(self):
        """Проверка .env файла."""
        print("\n🔐 Проверка .env...")

        if not Path(".env").exists():
            print("  ❌ Файл .env не найден")
            self.errors.append(".env файл отсутствует")
            return False

        # Проверка прав доступа
        stat = os.stat(".env")
        mode = stat.st_mode & 0o777
        if mode != 0o600:
            print(f"  ⚠️  Права доступа: {oct(mode)} (рекомендуется 0o600)")
            self.warnings.append(f".env имеет права {oct(mode)}, рекомендуется 600")
        else:
            print("  ✅ Права доступа: 600")

        # Проверка содержимого
        with open(".env", "r") as f:
            content = f.read()

        required_vars = [
            "ARGOS_NETWORK_SECRET",
            "ARGOS_MASTER_KEY",
        ]

        optional_vars = [
            "GEMINI_API_KEY",
            "TELEGRAM_BOT_TOKEN",
            "USER_ID",
        ]

        all_ok = True

        for var in required_vars:
            if var in content and not f"{var}=your_" in content:
                print(f"  ✅ {var}")
            else:
                print(f"  ❌ {var} не установлен")
                self.errors.append(f"{var} не настроен")
                all_ok = False

        for var in optional_vars:
            if var in content and not f"{var}=your_" in content:
                print(f"  ✅ {var}")
            else:
                print(f"  ⚠️  {var} не установлен")
                self.warnings.append(f"{var} не настроен")

        return all_ok

    def check_directories(self):
        """Проверка структуры директорий."""
        print("\n📁 Проверка директорий...")

        required_dirs = [
            "src",
            "config",
            "logs",
            "data",
        ]

        all_ok = True

        for dir_name in required_dirs:
            path = Path(dir_name)
            if path.exists():
                print(f"  ✅ {dir_name}/")
            else:
                print(f"  ⚠️  {dir_name}/ не существует (будет создана)")
                self.warnings.append(f"Директория {dir_name}/ отсутствует")

        return all_ok

    def check_ports(self):
        """Проверка доступности портов."""
        print("\n🔌 Проверка портов...")

        ports = [
            (8080, "Web Dashboard"),
            (55771, "P2P Network"),
        ]

        for port, description in ports:
            if self._is_port_available(port):
                print(f"  ✅ {port} ({description})")
            else:
                print(f"  ⚠️  {port} ({description}) занят")
                self.warnings.append(f"Порт {port} ({description}) занят")

        return True

    def _is_port_available(self, port):
        """Проверяет доступность порта."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False

    def check_files(self):
        """Проверка критичных файлов."""
        print("\n📄 Проверка файлов...")

        required_files = [
            "main.py",
            "genesis.py",
            "health_check.py",
            "requirements.txt",
        ]

        all_ok = True

        for file_name in required_files:
            path = Path(file_name)
            if path.exists():
                print(f"  ✅ {file_name}")
            else:
                print(f"  ❌ {file_name} не найден")
                self.errors.append(f"Файл {file_name} отсутствует")
                all_ok = False

        return all_ok

    def print_summary(self):
        """Выводит итоговую сводку."""
        print("\n" + "=" * 60)
        print("📊 ИТОГОВАЯ СВОДКА")
        print("=" * 60)

        if self.errors:
            print(f"\n❌ Ошибки ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️  Предупреждения ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
            print("Система готова к запуску.")
            return True
        elif not self.errors:
            print("\n✅ Критичных ошибок нет.")
            print(
                "Система может быть запущена, но рекомендуется устранить предупреждения."
            )
            return True
        else:
            print("\n❌ СИСТЕМА НЕ ГОТОВА К ЗАПУСКУ")
            print("\nРекомендуемые действия:")
            if ".env файл отсутствует" in self.errors:
                print("  1. Запустите: python setup_secrets.py")
            if any("не установлен" in e for e in self.errors):
                print("  2. Запустите: pip install -r requirements.txt")
            if any("не найден" in e for e in self.errors):
                print("  3. Убедитесь, что вы в корневой директории проекта")
            return False

    def run_full_check(self):
        """Запускает полную проверку."""
        print("🔍 ARGOS Readiness Check")
        print("=" * 60)

        checks = [
            self.check_python_version(),
            self.check_dependencies(),
            self.check_env_file(),
            self.check_directories(),
            self.check_ports(),
            self.check_files(),
        ]

        return self.print_summary()

    def run_quick_check(self):
        """Запускает быструю проверку."""
        print("⚡ ARGOS Quick Check")
        print("=" * 60)

        checks = [
            self.check_python_version(),
            self.check_env_file(),
            self.check_files(),
        ]

        return self.print_summary()

    def auto_fix(self):
        """Попытка автоматического исправления."""
        print("🔧 ARGOS Auto-Fix")
        print("=" * 60)

        # Создание директорий
        print("\n📁 Создание отсутствующих директорий...")
        for dir_name in ["config", "logs", "data", "builds/replicas"]:
            path = Path(dir_name)
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                print(f"  ✅ Создана {dir_name}/")

        # Исправление прав .env
        if Path(".env").exists():
            try:
                os.chmod(".env", 0o600)
                print("  ✅ Установлены права 600 для .env")
            except Exception as e:
                print(f"  ⚠️  Не удалось установить права: {e}")

        print("\n✅ Автоисправление завершено")
        print("Запустите проверку снова: python check_readiness.py")


def main():
    """Главная функция."""
    checker = ReadinessChecker()

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--quick":
            success = checker.run_quick_check()
        elif arg == "--fix":
            checker.auto_fix()
            return
        elif arg in ["--help", "-h"]:
            print(__doc__)
            return
        else:
            print(f"❌ Неизвестный аргумент: {arg}")
            print(__doc__)
            return
    else:
        success = checker.run_full_check()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
