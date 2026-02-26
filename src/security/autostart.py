"""
autostart.py — Регистрация Аргоса как системного сервиса
  Windows: Task Scheduler + реестр Run
  Linux:   systemd
  Android: BOOT_COMPLETED broadcast
"""
import os
import sys
import platform
import subprocess
import getpass

OS   = platform.system()
PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXE  = sys.executable

class ArgosAutostart:
    def __init__(self):
        self.os_type = OS
        self.app_path = PATH
        self.exe_path = EXE

    def install(self) -> str:
        if self.os_type == "Windows":
            return self._install_windows()
        elif self.os_type == "Linux":
            return self._install_linux()
        elif "ANDROID_ROOT" in os.environ:
            return self._install_android()
        return f"Автозапуск для {self.os_type} пока не реализован."

    def uninstall(self) -> str:
        if self.os_type == "Windows":
            return self._uninstall_windows()
        elif self.os_type == "Linux":
            return self._uninstall_linux()
        return "Удалено."

    def status(self) -> str:
        if self.os_type == "Windows":
            return self._status_windows()
        elif self.os_type == "Linux":
            return self._status_linux()
        return "Статус неизвестен."

    # ══════════════════════════════════════════════════════
    # WINDOWS
    # ══════════════════════════════════════════════════════
    def _install_windows(self) -> str:
        results = []

        # 1. Реестр: автозапуск при входе пользователя
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(
                key, "ArgosUniversalOS", 0, winreg.REG_SZ,
                f'"{self.exe_path}" "{os.path.join(self.app_path, "main.py")}"'
            )
            winreg.CloseKey(key)
            results.append("✅ Реестр HKLM\\Run — Аргос зарегистрирован")
        except Exception as e:
            results.append(f"⚠️ Реестр: {e} (нужны права администратора)")

        # 2. Task Scheduler — запуск при загрузке системы (до входа пользователя)
        try:
            task_xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <BootTrigger><Enabled>true</Enabled></BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
  <Actions>
    <Exec>
      <Command>"{self.exe_path}"</Command>
      <Arguments>"{os.path.join(self.app_path, 'main.py')}" --no-gui</Arguments>
      <WorkingDirectory>{self.app_path}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""
            xml_path = os.path.join(self.app_path, "argos_task.xml")
            with open(xml_path, "w", encoding="utf-16") as f:
                f.write(task_xml)

            result = subprocess.run(
                ["schtasks", "/Create", "/TN", "ArgosUniversalOS",
                 "/XML", xml_path, "/F"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                results.append("✅ Task Scheduler — задача создана (запуск при загрузке)")
            else:
                results.append(f"⚠️ Task Scheduler: {result.stderr.strip()[:100]}")
            os.remove(xml_path)
        except Exception as e:
            results.append(f"⚠️ Task Scheduler: {e}")

        return "\n".join(results)

    def _uninstall_windows(self) -> str:
        results = []
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, "ArgosUniversalOS")
            winreg.CloseKey(key)
            results.append("✅ Удалён из реестра")
        except Exception as e:
            results.append(f"⚠️ Реестр: {e}")

        try:
            subprocess.run(
                ["schtasks", "/Delete", "/TN", "ArgosUniversalOS", "/F"],
                capture_output=True
            )
            results.append("✅ Task Scheduler задача удалена")
        except Exception as e:
            results.append(f"⚠️ Task Scheduler: {e}")

        return "\n".join(results)

    def _status_windows(self) -> str:
        lines = ["🔄 АВТОЗАПУСК Windows:"]
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            try:
                val, _ = winreg.QueryValueEx(key, "ArgosUniversalOS")
                lines.append(f"  ✅ Реестр Run: {val[:60]}...")
            except FileNotFoundError:
                lines.append("  ❌ Реестр Run: не зарегистрирован")
            winreg.CloseKey(key)
        except Exception as e:
            lines.append(f"  ⚠️ Реестр: {e}")

        try:
            r = subprocess.run(
                ["schtasks", "/Query", "/TN", "ArgosUniversalOS", "/FO", "LIST"],
                capture_output=True, text=True
            )
            if r.returncode == 0:
                lines.append("  ✅ Task Scheduler: задача найдена")
            else:
                lines.append("  ❌ Task Scheduler: задача не найдена")
        except Exception:
            lines.append("  ⚠️ Task Scheduler: недоступен")

        return "\n".join(lines)

    # ══════════════════════════════════════════════════════
    # LINUX (systemd)
    # ══════════════════════════════════════════════════════
    def _install_linux(self) -> str:
        user    = getpass.getuser()
        svc_src = os.path.join(self.app_path, "argos.service")
        svc_dst = "/etc/systemd/system/argos.service"

        service = f"""[Unit]
Description=Argos Universal OS — AI System Service
After=network.target
Wants=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={self.app_path}
ExecStart={self.exe_path} {self.app_path}/main.py --no-gui
Restart=always
RestartSec=10
EnvironmentFile={self.app_path}/.env
StandardOutput=append:{self.app_path}/logs/service.log
StandardError=append:{self.app_path}/logs/service_error.log

[Install]
WantedBy=multi-user.target
"""
        with open(svc_src, "w") as f:
            f.write(service)

        try:
            subprocess.run(["sudo", "cp", svc_src, svc_dst], check=True)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            subprocess.run(["sudo", "systemctl", "enable", "argos"], check=True)
            subprocess.run(["sudo", "systemctl", "start",  "argos"], check=True)
            return (
                f"✅ systemd сервис установлен:\n"
                f"  sudo systemctl status argos\n"
                f"  sudo systemctl stop argos\n"
                f"  sudo journalctl -u argos -f"
            )
        except subprocess.CalledProcessError as e:
            return (
                f"⚠️ Не удалось установить через sudo.\n"
                f"Выполни вручную:\n"
                f"  sudo cp {svc_src} {svc_dst}\n"
                f"  sudo systemctl daemon-reload\n"
                f"  sudo systemctl enable argos\n"
                f"  sudo systemctl start argos"
            )

    def _uninstall_linux(self) -> str:
        try:
            subprocess.run(["sudo", "systemctl", "stop",    "argos"], check=True)
            subprocess.run(["sudo", "systemctl", "disable", "argos"], check=True)
            subprocess.run(["sudo", "rm", "/etc/systemd/system/argos.service"])
            subprocess.run(["sudo", "systemctl", "daemon-reload"])
            return "✅ Сервис argos остановлен и удалён."
        except Exception as e:
            return f"⚠️ {e}"

    def _status_linux(self) -> str:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", "argos"],
                capture_output=True, text=True
            )
            active = r.stdout.strip()
            r2 = subprocess.run(
                ["systemctl", "is-enabled", "argos"],
                capture_output=True, text=True
            )
            enabled = r2.stdout.strip()
            return (
                f"🔄 АВТОЗАПУСК Linux:\n"
                f"  Статус:   {active}\n"
                f"  Автостарт: {enabled}"
            )
        except Exception as e:
            return f"⚠️ systemctl недоступен: {e}"

    # ══════════════════════════════════════════════════════
    # ANDROID (через команды Termux/ADB)
    # ══════════════════════════════════════════════════════
    def _install_android(self) -> str:
        return (
            "📱 Android автозапуск:\n"
            "  Требует Termux + Termux:Boot\n\n"
            "  1. Установи: Termux + Termux:Boot из F-Droid\n"
            "  2. mkdir -p ~/.termux/boot\n"
            "  3. Создай ~/.termux/boot/argos.sh:\n"
            "     #!/data/data/com.termux/files/usr/bin/sh\n"
            f"     cd {self.app_path}\n"
            "     python main.py --no-gui\n"
            "  4. chmod +x ~/.termux/boot/argos.sh\n"
            "  Аргос запустится при загрузке Android."
        )
