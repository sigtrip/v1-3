"""
Telegram Bridge - удаленное управление Argos через Telegram.
"""

import os
from typing import Dict, Any, Optional, Callable
from datetime import datetime


class TelegramBridge:
    """Удаленный мост для управления через Telegram."""
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Инициализация Telegram моста.
        
        Args:
            token: Токен Telegram бота
            chat_id: ID чата для отправки сообщений
        """
        self.token = token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.is_configured = bool(self.token and self.chat_id)
        self.command_handlers = {}
    
    def configure(self, token: str, chat_id: str) -> Dict[str, Any]:
        """
        Настройка Telegram моста.
        
        Args:
            token: Токен бота
            chat_id: ID чата
            
        Returns:
            Результат настройки
        """
        self.token = token
        self.chat_id = chat_id
        self.is_configured = True
        
        return {
            'status': 'ok',
            'message': 'Telegram мост настроен'
        }
    
    def register_command(self, command: str, handler: Callable) -> None:
        """
        Регистрация обработчика команды.
        
        Args:
            command: Название команды
            handler: Функция-обработчик
        """
        self.command_handlers[command] = handler
    
    def send_message(self, message: str) -> Dict[str, Any]:
        """
        Отправка сообщения через Telegram.
        
        Args:
            message: Текст сообщения
            
        Returns:
            Результат отправки
        """
        if not self.is_configured:
            return {
                'status': 'error',
                'message': 'Telegram мост не настроен'
            }
        
        try:
            import requests
            
            url = f'https://api.telegram.org/bot{self.token}/sendMessage'
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                return {
                    'status': 'ok',
                    'message': 'Сообщение отправлено'
                }
            else:
                return {
                    'status': 'error',
                    'message': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_updates(self, offset: int = 0) -> Dict[str, Any]:
        """
        Получение обновлений от Telegram.
        
        Args:
            offset: Offset для получения новых сообщений
            
        Returns:
            Обновления
        """
        if not self.is_configured:
            return {
                'status': 'error',
                'message': 'Telegram мост не настроен'
            }
        
        try:
            import requests
            
            url = f'https://api.telegram.org/bot{self.token}/getUpdates'
            params = {'offset': offset, 'timeout': 30}
            
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                return {
                    'status': 'ok',
                    'updates': response.json().get('result', [])
                }
            else:
                return {
                    'status': 'error',
                    'message': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def start_polling(self, message_handler: Callable) -> None:
        """
        Запуск опроса обновлений (блокирующий).
        
        Args:
            message_handler: Функция обработки сообщений
        """
        if not self.is_configured:
            print('⚠️ Telegram мост не настроен')
            return
        
        print('🤖 Telegram мост запущен')
        offset = 0
        
        while True:
            try:
                updates = self.get_updates(offset)
                
                if updates['status'] == 'ok':
                    for update in updates['updates']:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            message = update['message']
                            message_handler(message)
            except KeyboardInterrupt:
                print('\n🛑 Остановка Telegram моста')
                break
            except Exception as e:
                print(f'❌ Ошибка: {e}')
    
    def get_status(self) -> Dict[str, Any]:
        """
        Получение статуса моста.
        
        Returns:
            Статус конфигурации
        """
        return {
            'configured': self.is_configured,
            'token_set': bool(self.token),
            'chat_id_set': bool(self.chat_id),
            'handlers_registered': len(self.command_handlers)
        }


def create_telegram_bridge(token: Optional[str] = None, chat_id: Optional[str] = None) -> TelegramBridge:
    """Фабричная функция для создания экземпляра TelegramBridge."""
    return TelegramBridge(token=token, chat_id=chat_id)
