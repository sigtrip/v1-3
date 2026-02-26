"""
Replicator - модуль для создания полной архивной копии системы.
"""

import os
import shutil
import tarfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


class Replicator:
    """Модуль репликации системы."""
    
    def __init__(self, base_path: str = '.'):
        self.base_path = Path(base_path)
        self.archive_dir = self.base_path / 'archives'
        self.archive_dir.mkdir(exist_ok=True)
    
    def create_archive(self, include_venv: bool = False) -> Dict[str, Any]:
        """
        Создание полной архивной копии системы.
        
        Args:
            include_venv: Включить ли виртуальное окружение в архив
            
        Returns:
            Результат операции
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f'argos_backup_{timestamp}.tar.gz'
            archive_path = self.archive_dir / archive_name
            
            # Список исключаемых директорий
            exclude_dirs = ['.git', '__pycache__', 'archives', 'backups', 'logs']
            if not include_venv:
                exclude_dirs.extend(['venv', '.venv', 'env'])
            
            # Создание архива
            with tarfile.open(archive_path, 'w:gz') as tar:
                for item in self.base_path.iterdir():
                    if item.name not in exclude_dirs and item.name != archive_path.name:
                        tar.add(item, arcname=item.name)
            
            archive_size = archive_path.stat().st_size
            
            return {
                'status': 'ok',
                'message': 'Архив создан успешно',
                'archive_name': archive_name,
                'archive_path': str(archive_path),
                'size': self._format_bytes(archive_size),
                'timestamp': timestamp
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def list_archives(self) -> Dict[str, Any]:
        """
        Список доступных архивов.
        
        Returns:
            Список архивов
        """
        try:
            archives = []
            
            for archive in self.archive_dir.glob('*.tar.gz'):
                stat = archive.stat()
                archives.append({
                    'name': archive.name,
                    'path': str(archive),
                    'size': self._format_bytes(stat.st_size),
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
            
            return {
                'status': 'ok',
                'archives': sorted(archives, key=lambda x: x['created'], reverse=True),
                'total': len(archives)
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def restore_archive(self, archive_name: str, target_dir: str = None) -> Dict[str, Any]:
        """
        Восстановление системы из архива.
        
        Args:
            archive_name: Имя архива для восстановления
            target_dir: Целевая директория (по умолчанию текущая)
            
        Returns:
            Результат операции
        """
        try:
            archive_path = self.archive_dir / archive_name
            
            if not archive_path.exists():
                return {
                    'status': 'error',
                    'message': f'Архив {archive_name} не найден'
                }
            
            target = Path(target_dir) if target_dir else self.base_path / f'restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            target.mkdir(parents=True, exist_ok=True)
            
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(target)
            
            return {
                'status': 'ok',
                'message': 'Архив восстановлен',
                'archive': archive_name,
                'target_dir': str(target)
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Форматирование байтов в читаемый вид."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"


def create_replicator(base_path: str = '.') -> Replicator:
    """Фабричная функция для создания экземпляра Replicator."""
    return Replicator(base_path=base_path)
