@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"

echo =============================================
echo   ARGOS Windows One-Click Run
echo =============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Виртуальное окружение не найдено. Запускаю install_windows.bat...
    if exist "install_windows.bat" (
        call install_windows.bat
        if errorlevel 1 goto :fail
    ) else (
        echo [ERROR] Не найден install_windows.bat.
        echo [INFO] Сначала запусти install_windows.bat вручную.
        goto :fail
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

echo [INFO] Инициализация структуры проекта...
"%VENV_PY%" genesis.py
if errorlevel 1 goto :fail

echo [INFO] Запуск ARGOS...
"%VENV_PY%" main.py %*
set "RUN_EXIT=%errorlevel%"

if not "%RUN_EXIT%"=="0" (
    echo [WARN] main.py завершился с кодом %RUN_EXIT%.
)

echo.
echo [DONE] Завершено.
exit /b %RUN_EXIT%

:fail
echo.
echo [FAIL] Запуск прерван из-за ошибки.
exit /b 1
