"""
Модуль администрирования Argos - управление системой, файлами и процессами.
Deep Admin - прямой доступ к ОС.
"""

import os
import psutil
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class SystemAdmin:
    """Администратор системы с глубоким доступом к ОС."""
    
    def __init__(self):
        self.platform = platform.system()
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Получение полной информации о состоянии системы.
        
        Returns:
            Словарь с данными о ЦП, ОЗУ, дисках и ОС
        """
        # Информация о CPU
        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
        cpu_freq = psutil.cpu_freq()
        
        # Информация о памяти
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Информация о дисках
        disk_partitions = psutil.disk_partitions()
        disk_usage = []
        for partition in disk_partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_usage.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'total': self._format_bytes(usage.total),
                    'used': self._format_bytes(usage.used),
                    'free': self._format_bytes(usage.free),
                    'percent': usage.percent
                })
            except PermissionError:
                continue
        
        # Информация об ОС
        uname = platform.uname()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'os': {
                'system': uname.system,
                'node': uname.node,
                'release': uname.release,
                'version': uname.version,
                'machine': uname.machine,
                'processor': uname.processor or 'Unknown'
            },
            'cpu': {
                'count': psutil.cpu_count(),
                'percent_per_core': cpu_percent,
                'percent_total': psutil.cpu_percent(interval=1),
                'frequency': {
                    'current': cpu_freq.current if cpu_freq else 0,
                    'min': cpu_freq.min if cpu_freq else 0,
                    'max': cpu_freq.max if cpu_freq else 0
                } if cpu_freq else None
            },
            'memory': {
                'total': self._format_bytes(memory.total),
                'available': self._format_bytes(memory.available),
                'used': self._format_bytes(memory.used),
                'percent': memory.percent
            },
            'swap': {
                'total': self._format_bytes(swap.total),
                'used': self._format_bytes(swap.used),
                'free': self._format_bytes(swap.free),
                'percent': swap.percent
            },
            'disks': disk_usage,
            'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }
    
    def list_files(self, path: str = '.') -> Dict[str, Any]:
        """
        Просмотр содержимого директории.
        
        Args:
            path: Путь к директории
            
        Returns:
            Информация о файлах и папках в директории
        """
        target_path = Path(path).resolve()
        
        if not target_path.exists():
            return {
                'status': 'error',
                'message': f'Путь {path} не существует'
            }
        
        if not target_path.is_dir():
            return {
                'status': 'error',
                'message': f'Путь {path} не является директорией'
            }
        
        items = []
        for item in target_path.iterdir():
            try:
                stat = item.stat()
                items.append({
                    'name': item.name,
                    'type': 'dir' if item.is_dir() else 'file',
                    'size': self._format_bytes(stat.st_size) if item.is_file() else '-',
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'permissions': oct(stat.st_mode)[-3:]
                })
            except PermissionError:
                items.append({
                    'name': item.name,
                    'type': 'unknown',
                    'error': 'Permission denied'
                })
        
        return {
            'status': 'ok',
            'path': str(target_path),
            'items': sorted(items, key=lambda x: (x['type'] != 'dir', x['name'])),
            'total': len(items)
        }
    
    def list_processes(self, filter_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение списка запущенных процессов.
        
        Args:
            filter_name: Фильтр по имени процесса (опционально)
            
        Returns:
            Список процессов с информацией
        """
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'memory_percent', 'cpu_percent']):
            try:
                pinfo = proc.info
                
                if filter_name and filter_name.lower() not in pinfo['name'].lower():
                    continue
                
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'username': pinfo['username'],
                    'memory_percent': round(pinfo['memory_percent'], 2),
                    'cpu_percent': round(pinfo['cpu_percent'], 2)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return sorted(processes, key=lambda x: x['memory_percent'], reverse=True)
    
    def kill_process(self, name: str) -> Dict[str, Any]:
        """
        Принудительное завершение процесса по имени.
        
        Args:
            name: Имя процесса для завершения
            
        Returns:
            Результат операции
        """
        killed = []
        errors = []
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if name.lower() in proc.info['name'].lower():
                    proc.kill()
                    killed.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                errors.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'error': str(e)
                })
        
        if not killed and not errors:
            return {
                'status': 'not_found',
                'message': f'Процесс "{name}" не найден'
            }
        
        return {
            'status': 'ok' if killed else 'error',
            'killed': killed,
            'errors': errors
        }
    
    def execute_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Выполнение системной команды.
        
        Args:
            command: Команда для выполнения
            timeout: Таймаут в секундах
            
        Returns:
            Результат выполнения команды
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                'status': 'ok' if result.returncode == 0 else 'error',
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': command
            }
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'message': f'Команда превысила таймаут {timeout} секунд',
                'command': command
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'command': command
            }
    
    def scan_anomalies(self) -> Dict[str, Any]:
        """
        Сканирование системы на наличие аномалий.
        
        Returns:
            Отчет об обнаруженных аномалиях
        """
        anomalies = []
        
        # Проверка высокой нагрузки на CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            anomalies.append({
                'type': 'high_cpu',
                'severity': 'warning',
                'message': f'Высокая загрузка CPU: {cpu_percent}%'
            })
        
        # Проверка использования памяти
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            anomalies.append({
                'type': 'high_memory',
                'severity': 'warning',
                'message': f'Высокое использование памяти: {memory.percent}%'
            })
        
        # Проверка использования диска
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                if usage.percent > 90:
                    anomalies.append({
                        'type': 'high_disk',
                        'severity': 'warning',
                        'message': f'Диск {partition.mountpoint} заполнен на {usage.percent}%'
                    })
            except PermissionError:
                continue
        
        # Проверка подозрительных процессов (высокое потребление ресурсов)
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if proc.info['cpu_percent'] > 80 or proc.info['memory_percent'] > 50:
                    anomalies.append({
                        'type': 'suspicious_process',
                        'severity': 'info',
                        'message': f'Процесс {proc.info["name"]} (PID: {proc.info["pid"]}) использует много ресурсов',
                        'details': {
                            'cpu': proc.info['cpu_percent'],
                            'memory': proc.info['memory_percent']
                        }
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {
            'timestamp': datetime.now().isoformat(),
            'anomalies_found': len(anomalies),
            'anomalies': anomalies,
            'status': 'clean' if not anomalies else 'anomalies_detected'
        }
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Форматирование байтов в читаемый вид."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"


def create_admin() -> SystemAdmin:
    """Фабричная функция для создания экземпляра SystemAdmin."""
    return SystemAdmin()
