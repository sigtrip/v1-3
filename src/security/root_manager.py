"""
root_manager.py — Root / привилегии Аргоса
  Linux: sudo/su
  Android: Magisk, su
  Windows: UAC elevation
"""
import os
import platform
import subprocess
import sys
from src.argos_logger import get_logger
log = get_logger("argos.root")

OS = platform.system()


class RootManager:
    def __init__(self):
        self.os_type    = OS
        self.is_android = "ANDROID_ROOT" in os.environ
        self._root_ok   = False

    @property
    def has_root(self) -> bool:
        if self._root_ok: return True
        if OS == "Linux" or self.is_android:
            return os.geteuid() == 0
        if OS == "Windows":
            try:
                import ctypes
                return bool(ctypes.windll.shell32.IsUserAnAdmin())
            except Exception:
                return False
        return False

    def check(self) -> str:
        lines = [f"🔐 ROOT СТАТУС ({self.os_type}):"]
        lines.append(f"  Root: {'✅ Да' if self.has_root else '❌ Нет'}")
        if self.is_android:
            try:
                r = subprocess.run(["su", "-c", "id"], capture_output=True, text=True, timeout=5)
                lines.append(f"  Android su: {'✅' if r.returncode == 0 else '❌'} {r.stdout.strip()[:60]}")
            except Exception as e:
                lines.append(f"  Android su: ❌ {e}")
        elif OS == "Linux":
            try:
                r = subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=3)
                lines.append(f"  sudo -n: {'✅ без пароля' if r.returncode == 0 else '⚠️ нужен пароль'}")
            except Exception as e:
                lines.append(f"  sudo: ❌ {e}")
            lines.append(f"  UID: {os.getuid()}")
        return "\n".join(lines)

    def run_as_root(self, cmd: str) -> str:
        """Запуск команды с правами root."""
        if self.is_android:
            try:
                r = subprocess.run(f"su -c \'{cmd}\'", shell=True,
                                   capture_output=True, text=True, timeout=30)
                return r.stdout.strip() or r.stderr.strip()
            except Exception as e:
                return f"❌ Android su: {e}"
        if OS == "Linux":
            try:
                r = subprocess.run(f"sudo {cmd}", shell=True,
                                   capture_output=True, text=True, timeout=30)
                return r.stdout.strip() or r.stderr.strip()
            except Exception as e:
                return f"❌ sudo: {e}"
        if OS == "Windows":
            try:
                import ctypes
                r = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", "cmd.exe", f"/c {cmd}", None, 0)
                return f"✅ Windows UAC запущен (код {r})"
            except Exception as e:
                return f"❌ UAC: {e}"
        return "❌ ОС не поддерживается"

    def request_root_android(self) -> str:
        """Запрашивает root на Android через Magisk."""
        try:
            r = subprocess.run(["su", "-c", "echo root_ok"],
                                capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and "root_ok" in r.stdout:
                self._root_ok = True
                return "✅ Android root получен (Magisk/su)"
            return "❌ Root запрос отклонён или Magisk не установлен."
        except Exception as e:
            return f"❌ su: {e}"

    def status(self) -> str:
        return self.check()
