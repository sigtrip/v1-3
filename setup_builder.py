"""
setup_builder.py — Генерация установщика setup.exe
  Создаёт NSIS-скрипт и собирает профессиональный Windows installer.

  Требования: NSIS (https://nsis.sourceforge.io)
  Запуск:
    python setup_builder.py          # генерирует setup.nsi
    python setup_builder.py --build  # генерирует И компилирует setup.exe
"""
import os
import sys
import subprocess
import platform
import datetime

VERSION = "1.0.0"
APP_NAME = "Argos Universal OS"

NSIS_SCRIPT = r"""
; ════════════════════════════════════════════════════════════
;  ARGOS UNIVERSAL OS — Windows Installer (NSIS)
;  Создан автоматически setup_builder.py
; ════════════════════════════════════════════════════════════

!define APP_NAME      "Argos Universal OS"
!define APP_VERSION   "1.0.0"
!define APP_EXE       "argos.exe"
!define INSTALL_DIR   "$PROGRAMFILES64\ArgosUniversalOS"
!define REG_KEY       "Software\Microsoft\Windows\CurrentVersion\Uninstall\ArgosUniversalOS"

; Метаданные
Name              "${APP_NAME} ${APP_VERSION}"
OutFile           "setup_argos.exe"
InstallDir        "${INSTALL_DIR}"
InstallDirRegKey  HKLM "${REG_KEY}" "InstallLocation"
RequestExecutionLevel admin    ; <-- ТРЕБУЕТ ПРАВА АДМИНИСТРАТОРА

; Современный интерфейс
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "assets\argos_icon.ico"
!define MUI_UNICON "assets\argos_icon.ico"
!define MUI_HEADERIMAGE
!define MUI_BGCOLOR "060A1A"
!define MUI_TEXTCOLOR "00FFFF"

; Страницы установки
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Страницы удаления
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "English"

; ════════════════════════════════════════════════════════════
Section "Argos Core" SecCore
    SectionIn RO    ; Обязательная секция

    SetOutPath "${INSTALL_DIR}"
    File /r "dist\argos\*.*"

    ; Копируем конфиги
    SetOutPath "${INSTALL_DIR}\config"
    File /nonfatal "config\identity.json"

    ; Создаём .env если нет
    IfFileExists "${INSTALL_DIR}\.env" env_exists
        FileOpen  $0 "${INSTALL_DIR}\.env" w
        FileWrite $0 "GEMINI_API_KEY=your_key_here$\r$\n"
        FileWrite $0 "TELEGRAM_BOT_TOKEN=your_token_here$\r$\n"
        FileWrite $0 "USER_ID=your_telegram_id$\r$\n"
        FileClose $0
    env_exists:

    ; Запись в реестр
    WriteRegStr   HKLM "${REG_KEY}" "DisplayName"     "${APP_NAME}"
    WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"   "${APP_VERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "Publisher"        "Vsevolod / Argos Project"
    WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"  "${INSTALL_DIR}"
    WriteRegStr   HKLM "${REG_KEY}" "UninstallString"  '"${INSTALL_DIR}\uninstall.exe"'
    WriteRegDWORD HKLM "${REG_KEY}" "NoModify"         1
    WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"         1

    ; Создаём деинсталлятор
    WriteUninstaller "${INSTALL_DIR}\uninstall.exe"
SectionEnd

; ════════════════════════════════════════════════════════════
Section "Ярлыки" SecShortcuts
    ; Рабочий стол
    CreateShortcut "$DESKTOP\Argos Universal OS.lnk" \
        "${INSTALL_DIR}\${APP_EXE}" "" \
        "${INSTALL_DIR}\${APP_EXE}" 0

    ; Меню Пуск
    CreateDirectory "$SMPROGRAMS\Argos Universal OS"
    CreateShortcut  "$SMPROGRAMS\Argos Universal OS\Argos.lnk" \
        "${INSTALL_DIR}\${APP_EXE}"
    CreateShortcut  "$SMPROGRAMS\Argos Universal OS\Удалить.lnk" \
        "${INSTALL_DIR}\uninstall.exe"
SectionEnd

; ════════════════════════════════════════════════════════════
Section "Автозапуск (Системный сервис)" SecService
    ; Регистрируем argos как Windows Service через NSSM
    ; (Non-Sucking Service Manager — скачивается автоматически)
    nsExec::ExecToLog '"${INSTALL_DIR}\nssm.exe" install ArgosService "${INSTALL_DIR}\${APP_EXE}" "--no-gui"'
    nsExec::ExecToLog '"${INSTALL_DIR}\nssm.exe" set ArgosService DisplayName "Argos Universal OS Service"'
    nsExec::ExecToLog '"${INSTALL_DIR}\nssm.exe" set ArgosService Description "Всевидящий ИИ-сервис Аргос"'
    nsExec::ExecToLog '"${INSTALL_DIR}\nssm.exe" set ArgosService Start SERVICE_AUTO_START'
    nsExec::ExecToLog '"${INSTALL_DIR}\nssm.exe" start ArgosService'

    ; Запись в автозапуск реестра (дублирование)
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Run" \
        "ArgosUniversalOS" '"${INSTALL_DIR}\${APP_EXE}"'
SectionEnd

; ════════════════════════════════════════════════════════════
Section "Uninstall"
    ; Останавливаем сервис
    nsExec::ExecToLog '"$INSTDIR\nssm.exe" stop ArgosService'
    nsExec::ExecToLog '"$INSTDIR\nssm.exe" remove ArgosService confirm'

    ; Убираем из автозапуска
    DeleteRegValue HKLM "Software\Microsoft\Windows\CurrentVersion\Run" "ArgosUniversalOS"

    ; Удаляем файлы
    RMDir /r "$INSTDIR"
    Delete   "$DESKTOP\Argos Universal OS.lnk"
    RMDir /r "$SMPROGRAMS\Argos Universal OS"

    ; Удаляем из реестра
    DeleteRegKey HKLM "${REG_KEY}"
SectionEnd
"""

LINUX_SERVICE = """[Unit]
Description=Argos Universal OS — AI System Service
After=network.target
Wants=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={path}
ExecStart=/usr/bin/python3 {path}/main.py --no-gui
Restart=always
RestartSec=10
Environment=DISPLAY=:0
EnvironmentFile={path}/.env

# Логирование
StandardOutput=append:{path}/logs/service.log
StandardError=append:{path}/logs/service_error.log

[Install]
WantedBy=multi-user.target
"""

def generate_nsis() -> str:
    path = "setup_argos.nsi"
    with open(path, "w", encoding="utf-8") as f:
        f.write(NSIS_SCRIPT)
    print(f"✅ NSIS-скрипт создан: {path}")
    return path

def build_setup() -> str:
    nsi = generate_nsis()
    nsis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
        "makensis",
    ]
    for nsis in nsis_paths:
        try:
            result = subprocess.run([nsis, "setup_argos.nsi"])
            if result.returncode == 0:
                size = os.path.getsize("setup_argos.exe") / (1024*1024)
                return f"✅ setup_argos.exe создан ({size:.1f} MB)"
        except FileNotFoundError:
            continue
    return "❌ NSIS не найден. Скачай: https://nsis.sourceforge.io\nNSIS-скрипт setup_argos.nsi готов к компиляции."

def generate_linux_service():
    import getpass
    user = getpass.getuser()
    path = os.path.abspath(".")
    service = LINUX_SERVICE.format(user=user, path=path)
    svc_path = "argos.service"
    with open(svc_path, "w") as f:
        f.write(service)
    print(f"✅ systemd-сервис создан: {svc_path}")
    print(f"\nДля установки:")
    print(f"  sudo cp {svc_path} /etc/systemd/system/")
    print(f"  sudo systemctl daemon-reload")
    print(f"  sudo systemctl enable argos")
    print(f"  sudo systemctl start argos")
    print(f"  sudo systemctl status argos")

def generate_license():
    lic = f"""Argos Universal OS — License Agreement

Copyright (c) 2026 Всеволод / Argos Project
Version: {VERSION}
Date: {datetime.date.today()}

Apache License 2.0

Licensed under the Apache License, Version 2.0.
You may use this software for commercial and personal purposes.
The author is not liable for damages caused by system administration features.

Creator: Всеволод
Project: Argos Universal OS v{VERSION}
"""
    with open("LICENSE", "w") as f:
        f.write(lic)
    print("✅ LICENSE создан")

if __name__ == "__main__":
    os_type = platform.system()
    
    if "--install" in sys.argv or "--deps" in sys.argv:
        install_deps()
        sys.exit(0)
    
    generate_license()

    if os_type == "Windows":
        if "--build" in sys.argv:
            print(build_setup())
        else:
            generate_nsis()
            print("\nДля сборки setup.exe:")
            print("  1. Установи NSIS: https://nsis.sourceforge.io")
            print("  2. python setup_builder.py --build")
            print("  ИЛИ python build_exe.py  →  потом  python setup_builder.py --build")
    elif os_type == "Linux":
        generate_linux_service()
    else:
        print(f"ОС {os_type}: генерирую NSIS-скрипт для Windows...")
        generate_nsis()
