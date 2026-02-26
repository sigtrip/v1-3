#!/usr/bin/env python3
"""
Argos Universal OS - Main Orchestrator
Главный оркестратор системы Argos.
"""

import sys
import json
from pathlib import Path
from src.core import create_argos_core


def print_banner():
    """Вывод баннера Argos."""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          👁️  ARGOS UNIVERSAL OS (v1.0.0-Absolute)        ║
    ║                                                           ║
    ║        "Аргос — всевидящий, всезнающий, неизменный."     ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    
    Система: ONLINE
    Создатель: Всеволод
    Год: 2026
    """
    print(banner)


def format_response(response: dict) -> str:
    """
    Форматирование ответа для вывода.
    
    Args:
        response: Ответ от ядра
        
    Returns:
        Отформатированная строка
    """
    if response['status'] == 'ok':
        if 'data' in response:
            return json.dumps(response['data'], ensure_ascii=False, indent=2)
        return response.get('message', 'Команда выполнена')
    elif response['status'] == 'error':
        return f"❌ Ошибка: {response.get('message', 'Неизвестная ошибка')}"
    elif response['status'] == 'unknown':
        return f"⚠️  {response.get('message', 'Команда не распознана')}"
    else:
        return json.dumps(response, ensure_ascii=False, indent=2)


def interactive_mode(argos: object):
    """
    Интерактивный режим работы с Argos.
    
    Args:
        argos: Экземпляр ArgosCore
    """
    print("\n🤖 Argos готов к работе. Введите 'помощь' для списка команд или 'выход' для завершения.\n")
    
    while True:
        try:
            user_input = input("👤 Команда: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['выход', 'exit', 'quit']:
                print("\n👋 До свидания!")
                break
            
            # Обработка команды
            response = argos.process_command(user_input)
            
            # Вывод результата
            print(f"\n🤖 Argos:\n{format_response(response)}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break
        except Exception as e:
            print(f"\n❌ Критическая ошибка: {e}\n")


def execute_protocol_zero(argos: object):
    """
    Выполнение протокола "Нулевой Пациент" - полная инициализация.
    
    Args:
        argos: Экземпляр ArgosCore
    """
    print("\n🛡️  Запуск протокола 'Нулевой Пациент'...\n")
    
    # Инициализация всех протоколов
    report = argos.initialize_protocols()
    
    print("📋 Отчет об инициализации:\n")
    print(f"⏰ Время: {report['timestamp']}")
    print(f"🆔 Личность: {report['identity']['name']} v{report['identity']['version']}")
    print(f"👤 Создатель: {report['identity']['creator']}\n")
    
    print("📊 Статус протоколов:\n")
    for protocol in report['protocols']:
        status_icon = '✅' if protocol['status'] in ['ok', 'active', 'online', 'clean'] else '⚠️'
        print(f"  {status_icon} {protocol['name']}: {protocol['status']}")
    
    print("\n🎯 Система готова к защите и мониторингу.\n")


def main():
    """Главная функция оркестратора."""
    print_banner()
    
    # Проверка наличия config/identity.json
    config_path = Path('config/identity.json')
    if not config_path.exists():
        print("⚠️  Файл конфигурации не найден. Запустите 'python genesis.py' для инициализации.")
        return
    
    # Создание ядра Argos
    try:
        argos = create_argos_core()
    except Exception as e:
        print(f"❌ Ошибка инициализации ядра: {e}")
        return
    
    # Парсинг аргументов командной строки
    if len(sys.argv) > 1:
        command = ' '.join(sys.argv[1:])
        
        # Специальная команда для протокола "Нулевой Пациент"
        if 'протокол' in command.lower() and 'нулевой' in command.lower():
            execute_protocol_zero(argos)
        else:
            response = argos.process_command(command)
            print(format_response(response))
    else:
        # Интерактивный режим
        interactive_mode(argos)


if __name__ == '__main__':
    main()
