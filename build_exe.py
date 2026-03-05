"""
build_exe.py — Сборка Argos Universal OS в .exe / бинарник
  Использует PyInstaller для упаковки всего проекта.

  Запуск:
    python build_exe.py          # сборка для текущей ОС
    python build_exe.py --onedir # папка вместо одного файла
"""

import os
import sys
import subprocess
import platform
import shutil
import importlib.util

OS = platform.system()

# Иконка (если есть)
ICON_PATH = "assets/argos_icon.ico" if OS == "Windows" else "assets/argos_icon.icns"
ICON_ARG = f"--icon={ICON_PATH}" if os.path.exists(ICON_PATH) else ""

# Скрытые импорты — модули которые PyInstaller может не увидеть
HIDDEN = [
    "customtkinter",
    "google.genai",
    "ollama",
    "pyttsx3",
    "speech_recognition",
    "cryptography.fernet",
    "serial.tools.list_ports",
    "psutil",
    "bs4",
    "telegram",
    "kivy",
    "sqlite3",
]


def build():
    print(f"[BUILD]: ОС: {OS}")
    print(f"[BUILD]: Сборка argos.exe...")

    # Проверяем PyInstaller
    if importlib.util.find_spec("PyInstaller") is None:
        print("[BUILD]: Устанавливаю PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    mode = "--onefile" if "--onedir" not in sys.argv else "--onedir"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        mode,
        "--name",
        "argos",
        "--clean",
        "--noconfirm",
        # Данные
        "--add-data",
        f"src{os.pathsep}src",
        "--add-data",
        f"config{os.pathsep}config",
        "--add-data",
        f"assets{os.pathsep}assets",
        # Скрытые импорты
        *[arg for h in HIDDEN for arg in ("--hidden-import", h)],
        # Консоль (False = без чёрного окна на Windows)
        "--console",
    ]

    if os.path.exists(".env"):
        cmd += ["--add-data", f".env{os.pathsep}."]

    if ICON_ARG:
        cmd.append(ICON_ARG)

    # Манифест Windows (запрос прав администратора при запуске)
    if OS == "Windows":
        manifest = _create_manifest()
        cmd += ["--manifest", manifest]

    cmd.append("main.py")

    print("[BUILD]: Запуск PyInstaller...")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe = "dist/argos.exe" if OS == "Windows" else "dist/argos"
        size = os.path.getsize(exe) / (1024 * 1024) if os.path.exists(exe) else 0
        run_cmd = "dist\\argos.exe" if OS == "Windows" else "./dist/argos"
        print(f"\n✅ ГОТОВО: {exe} ({size:.1f} MB)")
        print(f"   Запуск: {run_cmd}")
    else:
        print("\n❌ Сборка завершилась с ошибкой.")


def _create_manifest() -> str:
    """Создаёт Windows-манифест для запроса прав администратора."""
    content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity version="1.0.0.0" name="ArgosUniversalOS" type="win32"/>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
    </application>
  </compatibility>
</assembly>"""
    path = "assets/argos.manifest"
    os.makedirs("assets", exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return path


if __name__ == "__main__":
    build()
