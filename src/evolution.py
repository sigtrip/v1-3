"""
Модуль эволюции Argos - самозапись и самообновление кода.
Позволяет системе адаптироваться и расширять свои возможности.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class Evolution:
    """Модуль самозаписи и эволюции кода."""
    
    def __init__(self, base_path: str = '.'):
        self.base_path = Path(base_path)
        self.evolution_log = self.base_path / 'logs' / 'evolution.log'
        self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        """Создание директории для логов если её нет."""
        log_dir = self.base_path / 'logs'
        log_dir.mkdir(exist_ok=True)
    
    def log_evolution(self, action: str, details: Dict[str, Any]):
        """
        Логирование эволюционных изменений.
        
        Args:
            action: Тип действия
            details: Детали изменения
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'details': details
        }
        
        with open(self.evolution_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def create_module(self, name: str, code: str, location: str = 'src/skills') -> Dict[str, Any]:
        """
        Создание нового модуля.
        
        Args:
            name: Имя модуля
            code: Код модуля
            location: Расположение модуля
            
        Returns:
            Результат операции
        """
        try:
            module_path = self.base_path / location / f"{name}.py"
            module_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(module_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            self.log_evolution('module_created', {
                'name': name,
                'path': str(module_path),
                'size': len(code)
            })
            
            return {
                'status': 'ok',
                'message': f'Модуль {name} создан',
                'path': str(module_path)
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def update_identity(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обновление файла личности.
        
        Args:
            updates: Обновления для применения
            
        Returns:
            Результат операции
        """
        try:
            identity_path = self.base_path / 'config' / 'identity.json'
            
            if identity_path.exists():
                with open(identity_path, 'r', encoding='utf-8') as f:
                    identity = json.load(f)
            else:
                identity = {}
            
            # Применение обновлений
            identity.update(updates)
            
            with open(identity_path, 'w', encoding='utf-8') as f:
                json.dump(identity, f, ensure_ascii=False, indent=2)
            
            self.log_evolution('identity_updated', updates)
            
            return {
                'status': 'ok',
                'message': 'Личность обновлена',
                'updates': updates
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def backup_system(self) -> Dict[str, Any]:
        """
        Создание резервной копии критичных файлов.
        
        Returns:
            Результат операции
        """
        try:
            backup_dir = self.base_path / 'backups' / datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Копирование критичных файлов
            critical_files = [
                'config/identity.json',
                'src/core.py',
                'main.py'
            ]
            
            backed_up = []
            for file_path in critical_files:
                source = self.base_path / file_path
                if source.exists():
                    dest = backup_dir / file_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    
                    import shutil
                    shutil.copy2(source, dest)
                    backed_up.append(file_path)
            
            self.log_evolution('backup_created', {
                'backup_dir': str(backup_dir),
                'files': backed_up
            })
            
            return {
                'status': 'ok',
                'message': 'Резервная копия создана',
                'backup_dir': str(backup_dir),
                'files': backed_up
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_evolution_history(self, limit: int = 10) -> Dict[str, Any]:
        """
        Получение истории эволюции.
        
        Args:
            limit: Количество последних записей
            
        Returns:
            История изменений
        """
        try:
            if not self.evolution_log.exists():
                return {
                    'status': 'ok',
                    'history': [],
                    'message': 'История пуста'
                }
            
            with open(self.evolution_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Получение последних записей
            recent = lines[-limit:] if len(lines) > limit else lines
            history = [json.loads(line) for line in recent]
            
            return {
                'status': 'ok',
                'history': history,
                'total': len(lines)
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }


def create_evolution(base_path: str = '.') -> Evolution:
    """Фабричная функция для создания экземпляра Evolution."""
    return Evolution(base_path=base_path)
