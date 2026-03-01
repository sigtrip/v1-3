"""
connectivity — Модули связи и периферии Аргоса.
"""
from .nfc_manager import NFCManager, get_nfc_manager
from .usb_diagnostics import USBDiagnostics, get_usb_diagnostics
from .bluetooth_scanner import ArgosBluetoothScanner

__all__ = [
    "NFCManager", "get_nfc_manager",
    "USBDiagnostics", "get_usb_diagnostics",
    "ArgosBluetoothScanner",
]
