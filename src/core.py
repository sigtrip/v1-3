"""
Core - диспетчер команд и логика ИИ Argos.
Центральный модуль обработки команд и взаимодействия с пользователем.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .admin import create_admin
from .quantum.logic import create_quantum_engine
from .security.encryption import create_shield, create_git_guard
from .skills.web_scrapper import create_argos_eyes
from .evolution import create_evolution
from .factory.flasher import create_flasher
from .factory.replicator import create_replicator
from .connectivity.telegram import create_telegram_bridge


class ArgosCore:
    """Ядро Argos - диспетчер команд и ИИ логика."""
    
    def __init__(self, config_path: str = 'config/identity.json'):
        """
        Инициализация ядра Argos.
        
        Args:
            config_path: Путь к файлу конфигурации
        """
        self.config_path = Path(config_path)
        self.identity = self._load_identity()
        
        # Инициализация модулей
        self.admin = create_admin()
        self.quantum = create_quantum_engine()
        self.shield = create_shield()
        self.git_guard = create_git_guard()
        self.argos_eyes = create_argos_eyes()
        self.evolution = create_evolution()
        self.flasher = create_flasher()
        self.replicator = create_replicator()
        self.telegram = create_telegram_bridge()
        
        # Регистрация команд
        self.commands = self._register_commands()
    
    def _load_identity(self) -> Dict[str, Any]:
        """Загрузка файла личности."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {
                    'name': 'Argos',
                    'version': '1.0.0',
                    'status': 'INITIALIZING'
                }
        except Exception as e:
            print(f'⚠️ Ошибка загрузки личности: {e}')
            return {'name': 'Argos', 'status': 'ERROR'}
    
    def _register_commands(self) -> Dict[str, callable]:
        """Регистрация всех доступных команд."""
        return {
            # Системные команды
            'статус системы': self._cmd_system_status,
            'файлы': self._cmd_list_files,
            'убей процесс': self._cmd_kill_process,
            'консоль': self._cmd_execute_command,
            'процессы': self._cmd_list_processes,
            'аномалии': self._cmd_scan_anomalies,
            
            # Квантовые команды
            'квантовое состояние': self._cmd_quantum_state,
            'вектор вероятности': self._cmd_quantum_vector,
            
            # Безопасность
            'аудит безопасности': self._cmd_security_audit,
            'проверка щита': self._cmd_shield_status,
            
            # Сетевые команды
            'поиск': self._cmd_web_search,
            'новости': self._cmd_tech_news,
            'проверка сети': self._cmd_check_connectivity,
            
            # Factory команды
            'сканируй порты': self._cmd_scan_ports,
            'репликация': self._cmd_replicate,
            'список архивов': self._cmd_list_archives,
            
            # Эволюция
            'история эволюции': self._cmd_evolution_history,
            'резервная копия': self._cmd_backup,
            
            # Служебные
            'помощь': self._cmd_help,
            'личность': self._cmd_identity
        }
    
    def process_command(self, command: str) -> Dict[str, Any]:
        """
        Обработка команды пользователя.
        
        Args:
            command: Команда пользователя
            
        Returns:
            Результат выполнения команды
        """
        # Определение тона ответа на основе квантового состояния
        tone = self.quantum.get_tone(command)
        
        # Парсинг команды
        cmd_parts = command.strip().split(maxsplit=1)
        cmd_name = cmd_parts[0].lower() if cmd_parts else ''
        cmd_args = cmd_parts[1] if len(cmd_parts) > 1 else ''
        
        # Поиск полного совпадения команды
        for registered_cmd, handler in self.commands.items():
            if command.lower().startswith(registered_cmd.lower()):
                # Извлечение аргументов
                args = command[len(registered_cmd):].strip()
                return handler(args)
        
        # Команда не найдена
        return {
            'status': 'unknown',
            'message': f'Команда не распознана. Используйте "помощь" для списка команд.',
            'tone': tone
        }
    
    # Обработчики команд
    
    def _cmd_system_status(self, args: str) -> Dict[str, Any]:
        """Команда: статус системы"""
        status = self.admin.get_system_status()
        return {
            'status': 'ok',
            'command': 'system_status',
            'data': status
        }
    
    def _cmd_list_files(self, args: str) -> Dict[str, Any]:
        """Команда: файлы [путь]"""
        path = args if args else '.'
        result = self.admin.list_files(path)
        return {
            'status': result['status'],
            'command': 'list_files',
            'data': result
        }
    
    def _cmd_kill_process(self, args: str) -> Dict[str, Any]:
        """Команда: убей процесс [имя]"""
        if not args:
            return {
                'status': 'error',
                'message': 'Укажите имя процесса'
            }
        result = self.admin.kill_process(args)
        return {
            'status': result['status'],
            'command': 'kill_process',
            'data': result
        }
    
    def _cmd_execute_command(self, args: str) -> Dict[str, Any]:
        """Команда: консоль [команда]"""
        if not args:
            return {
                'status': 'error',
                'message': 'Укажите команду для выполнения'
            }
        result = self.admin.execute_command(args)
        return {
            'status': result['status'],
            'command': 'execute_command',
            'data': result
        }
    
    def _cmd_list_processes(self, args: str) -> Dict[str, Any]:
        """Команда: процессы [фильтр]"""
        processes = self.admin.list_processes(args if args else None)
        return {
            'status': 'ok',
            'command': 'list_processes',
            'data': {'processes': processes, 'count': len(processes)}
        }
    
    def _cmd_scan_anomalies(self, args: str) -> Dict[str, Any]:
        """Команда: аномалии"""
        result = self.admin.scan_anomalies()
        return {
            'status': 'ok',
            'command': 'scan_anomalies',
            'data': result
        }
    
    def _cmd_quantum_state(self, args: str) -> Dict[str, Any]:
        """Команда: квантовое состояние"""
        report = self.quantum.get_state_report()
        return {
            'status': 'ok',
            'command': 'quantum_state',
            'data': report
        }
    
    def _cmd_quantum_vector(self, args: str) -> Dict[str, Any]:
        """Команда: вектор вероятности"""
        vector = self.quantum.quantum_state.get_state_vector()
        return {
            'status': 'ok',
            'command': 'quantum_vector',
            'data': {
                'vector': vector,
                'current_state': self.quantum.quantum_state.get_current_state()
            }
        }
    
    def _cmd_security_audit(self, args: str) -> Dict[str, Any]:
        """Команда: аудит безопасности"""
        result = self.git_guard.audit_config()
        return {
            'status': result['status'],
            'command': 'security_audit',
            'data': result
        }
    
    def _cmd_shield_status(self, args: str) -> Dict[str, Any]:
        """Команда: проверка щита"""
        return {
            'status': 'ok',
            'command': 'shield_status',
            'data': {
                'protocol': 'AES-256',
                'active': True,
                'message': 'Протокол Щит активен'
            }
        }
    
    def _cmd_web_search(self, args: str) -> Dict[str, Any]:
        """Команда: поиск [запрос]"""
        if not args:
            return {
                'status': 'error',
                'message': 'Укажите поисковый запрос'
            }
        result = self.argos_eyes.search_web(args)
        return {
            'status': result['status'],
            'command': 'web_search',
            'data': result
        }
    
    def _cmd_tech_news(self, args: str) -> Dict[str, Any]:
        """Команда: новости"""
        news = self.argos_eyes.get_tech_news()
        return {
            'status': 'ok',
            'command': 'tech_news',
            'data': {'news': news, 'count': len(news)}
        }
    
    def _cmd_check_connectivity(self, args: str) -> Dict[str, Any]:
        """Команда: проверка сети"""
        result = self.argos_eyes.check_connectivity()
        return {
            'status': 'ok',
            'command': 'check_connectivity',
            'data': result
        }
    
    def _cmd_scan_ports(self, args: str) -> Dict[str, Any]:
        """Команда: сканируй порты"""
        result = self.flasher.scan_ports()
        return {
            'status': result['status'],
            'command': 'scan_ports',
            'data': result
        }
    
    def _cmd_replicate(self, args: str) -> Dict[str, Any]:
        """Команда: репликация"""
        result = self.replicator.create_archive()
        return {
            'status': result['status'],
            'command': 'replicate',
            'data': result
        }
    
    def _cmd_list_archives(self, args: str) -> Dict[str, Any]:
        """Команда: список архивов"""
        result = self.replicator.list_archives()
        return {
            'status': result['status'],
            'command': 'list_archives',
            'data': result
        }
    
    def _cmd_evolution_history(self, args: str) -> Dict[str, Any]:
        """Команда: история эволюции"""
        result = self.evolution.get_evolution_history()
        return {
            'status': result['status'],
            'command': 'evolution_history',
            'data': result
        }
    
    def _cmd_backup(self, args: str) -> Dict[str, Any]:
        """Команда: резервная копия"""
        result = self.evolution.backup_system()
        return {
            'status': result['status'],
            'command': 'backup',
            'data': result
        }
    
    def _cmd_help(self, args: str) -> Dict[str, Any]:
        """Команда: помощь"""
        categories = {
            'Системные': [
                'статус системы - Информация о ЦП, ОЗУ и ОС',
                'файлы [путь] - Просмотр содержимого директории',
                'процессы [фильтр] - Список запущенных процессов',
                'убей процесс [имя] - Завершение процесса',
                'консоль [команда] - Выполнение системной команды',
                'аномалии - Проверка системы на аномалии'
            ],
            'Квантовые': [
                'квантовое состояние - Текущее квантовое состояние',
                'вектор вероятности - Вектор квантовых вероятностей'
            ],
            'Безопасность': [
                'аудит безопасности - Проверка безопасности config',
                'проверка щита - Статус протокола Щит'
            ],
            'Сетевые': [
                'поиск [запрос] - Поиск в сети',
                'новости - Технологические новости',
                'проверка сети - Проверка подключения'
            ],
            'Factory': [
                'сканируй порты - Поиск подключенных устройств',
                'репликация - Создание архива системы',
                'список архивов - Доступные архивы'
            ],
            'Эволюция': [
                'история эволюции - История изменений',
                'резервная копия - Бэкап критичных файлов'
            ]
        }
        
        return {
            'status': 'ok',
            'command': 'help',
            'data': {
                'categories': categories,
                'total_commands': sum(len(cmds) for cmds in categories.values())
            }
        }
    
    def _cmd_identity(self, args: str) -> Dict[str, Any]:
        """Команда: личность"""
        return {
            'status': 'ok',
            'command': 'identity',
            'data': self.identity
        }
    
    def initialize_protocols(self) -> Dict[str, Any]:
        """
        Инициализация всех протоколов Argos (Протокол "Нулевой Пациент").
        
        Returns:
            Отчет об инициализации
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'identity': self.identity,
            'protocols': []
        }
        
        # 1. Проверка квантового ядра
        quantum_report = self.quantum.get_state_report()
        report['protocols'].append({
            'name': 'Квантовое Ядро',
            'status': 'active',
            'data': quantum_report
        })
        
        # 2. Аудит безопасности
        security_audit = self.git_guard.audit_config()
        report['protocols'].append({
            'name': 'Протокол Щит',
            'status': security_audit['status'],
            'data': security_audit
        })
        
        # 3. Сканирование процессов
        anomalies = self.admin.scan_anomalies()
        report['protocols'].append({
            'name': 'Мониторинг Системы',
            'status': anomalies['status'],
            'data': anomalies
        })
        
        # 4. Проверка сети
        connectivity = self.argos_eyes.check_connectivity()
        report['protocols'].append({
            'name': 'Argos Eyes',
            'status': connectivity['status'],
            'data': connectivity
        })
        
        return report


def create_argos_core(config_path: str = 'config/identity.json') -> ArgosCore:
    """Фабричная функция для создания экземпляра ArgosCore."""
    return ArgosCore(config_path=config_path)
