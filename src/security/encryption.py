"""
Модуль безопасности Argos - шифрование AES-256 и защита данных.
Протокол "Щит" для защиты конфиденциальной информации.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import base64


class Shield:
    """Протокол "Щит" - система шифрования AES-256."""
    
    def __init__(self, key: Optional[bytes] = None):
        """
        Инициализация щита с ключом шифрования.
        
        Args:
            key: 32-байтовый ключ для AES-256. Если не указан, генерируется новый.
        """
        self.key = key if key else self._generate_key()
        self.backend = default_backend()
    
    def _generate_key(self) -> bytes:
        """Генерация нового 256-битного ключа."""
        return os.urandom(32)
    
    def _generate_iv(self) -> bytes:
        """Генерация вектора инициализации."""
        return os.urandom(16)
    
    def encrypt(self, data: str) -> str:
        """
        Шифрование данных с использованием AES-256-CBC.
        
        Args:
            data: Строка для шифрования
            
        Returns:
            Base64-кодированная строка с IV + зашифрованными данными
        """
        # Генерация IV
        iv = self._generate_iv()
        
        # Создание шифра
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()
        
        # Паддинг данных
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data.encode('utf-8')) + padder.finalize()
        
        # Шифрование
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        
        # Объединение IV и зашифрованных данных
        result = iv + encrypted
        
        # Base64 кодирование
        return base64.b64encode(result).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Дешифрование данных.
        
        Args:
            encrypted_data: Base64-кодированная строка с зашифрованными данными
            
        Returns:
            Расшифрованная строка
        """
        # Декодирование Base64
        data = base64.b64decode(encrypted_data)
        
        # Извлечение IV и зашифрованных данных
        iv = data[:16]
        encrypted = data[16:]
        
        # Создание дешифратора
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        
        # Дешифрование
        decrypted_padded = decryptor.update(encrypted) + decryptor.finalize()
        
        # Удаление паддинга
        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()
        
        return decrypted.decode('utf-8')
    
    def save_key(self, filepath: str) -> None:
        """Сохранение ключа в файл."""
        with open(filepath, 'wb') as f:
            f.write(self.key)
    
    @classmethod
    def load_key(cls, filepath: str) -> 'Shield':
        """Загрузка ключа из файла."""
        with open(filepath, 'rb') as f:
            key = f.read()
        return cls(key=key)


class GitGuard:
    """Автоматическая проверка безопасности репозитория."""
    
    SENSITIVE_PATTERNS = [
        'password',
        'api_key',
        'secret',
        'token',
        'private_key',
        'ssh_key',
        'credentials'
    ]
    
    def __init__(self, repo_path: str = '.'):
        self.repo_path = Path(repo_path)
    
    def scan_directory(self, directory: Path) -> Dict[str, list]:
        """
        Сканирование директории на наличие потенциально чувствительных данных.
        
        Args:
            directory: Путь к директории для сканирования
            
        Returns:
            Словарь с найденными потенциальными проблемами
        """
        issues = {
            'sensitive_files': [],
            'large_files': [],
            'suspicious_content': []
        }
        
        for file_path in directory.rglob('*'):
            if file_path.is_file() and not self._is_ignored(file_path):
                # Проверка на чувствительные имена файлов
                if any(pattern in file_path.name.lower() for pattern in self.SENSITIVE_PATTERNS):
                    issues['sensitive_files'].append(str(file_path))
                
                # Проверка размера файла (> 10MB)
                if file_path.stat().st_size > 10 * 1024 * 1024:
                    issues['large_files'].append(str(file_path))
                
                # Проверка содержимого текстовых файлов
                if file_path.suffix in ['.py', '.js', '.json', '.txt', '.md', '.yml', '.yaml']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            for pattern in self.SENSITIVE_PATTERNS:
                                if pattern in content.lower():
                                    issues['suspicious_content'].append({
                                        'file': str(file_path),
                                        'pattern': pattern
                                    })
                    except:
                        pass  # Пропускаем файлы, которые не могут быть прочитаны
        
        return issues
    
    def _is_ignored(self, path: Path) -> bool:
        """Проверка, должен ли файл быть проигнорирован."""
        ignored = ['.git', '__pycache__', '.venv', 'venv', 'node_modules']
        return any(part in str(path) for part in ignored)
    
    def audit_config(self, config_dir: str = 'config') -> Dict[str, any]:
        """
        Аудит директории конфигурации.
        
        Args:
            config_dir: Путь к директории конфигурации
            
        Returns:
            Отчет об аудите
        """
        config_path = self.repo_path / config_dir
        
        if not config_path.exists():
            return {
                'status': 'error',
                'message': f'Директория {config_dir} не найдена'
            }
        
        issues = self.scan_directory(config_path)
        
        return {
            'status': 'ok' if not any(issues.values()) else 'warning',
            'directory': str(config_path),
            'issues': issues,
            'files_scanned': len(list(config_path.rglob('*')))
        }


def create_shield(key: Optional[bytes] = None) -> Shield:
    """Фабричная функция для создания экземпляра Shield."""
    return Shield(key=key)


def create_git_guard(repo_path: str = '.') -> GitGuard:
    """Фабричная функция для создания экземпляра GitGuard."""
    return GitGuard(repo_path=repo_path)
