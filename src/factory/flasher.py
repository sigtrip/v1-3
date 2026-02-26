"""
Flasher - модуль для прошивки IoT устройств и поиска контроллеров.
"""

import serial.tools.list_ports
from typing import List, Dict, Any


class Flasher:
    """Модуль прошивки IoT и поиска контроллеров."""
    
    def __init__(self):
        pass
    
    def scan_ports(self) -> Dict[str, Any]:
        """
        Сканирование доступных портов на наличие устройств.
        
        Returns:
            Список найденных портов и устройств
        """
        try:
            ports = serial.tools.list_ports.comports()
            devices = []
            
            for port in ports:
                devices.append({
                    'port': port.device,
                    'description': port.description,
                    'hwid': port.hwid,
                    'manufacturer': port.manufacturer or 'Unknown',
                    'product': port.product or 'Unknown',
                    'serial_number': port.serial_number or 'Unknown'
                })
            
            return {
                'status': 'ok',
                'devices_found': len(devices),
                'devices': devices
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_device_info(self, port: str) -> Dict[str, Any]:
        """
        Получение информации об устройстве на конкретном порту.
        
        Args:
            port: Имя порта (например, COM3, /dev/ttyUSB0)
            
        Returns:
            Информация об устройстве
        """
        try:
            ports = serial.tools.list_ports.comports()
            
            for p in ports:
                if p.device == port:
                    return {
                        'status': 'ok',
                        'port': p.device,
                        'description': p.description,
                        'hwid': p.hwid,
                        'manufacturer': p.manufacturer or 'Unknown',
                        'product': p.product or 'Unknown',
                        'serial_number': p.serial_number or 'Unknown',
                        'vid': p.vid,
                        'pid': p.pid
                    }
            
            return {
                'status': 'not_found',
                'message': f'Устройство на порту {port} не найдено'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }


def create_flasher() -> Flasher:
    """Фабричная функция для создания экземпляра Flasher."""
    return Flasher()
