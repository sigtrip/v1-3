@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"

echo =============================================
echo   ARGOS Windows Bootstrap Installer
echo =============================================
echo.

call :detect_python
if errorlevel 1 (
    echo [INFO] Python не найден. Пытаюсь установить через winget...
    call :install_python_winget
    if errorlevel 1 (
        echo [WARN] winget недоступен или установка не удалась. Пробую официальный installer...
        call :install_python_fallback
        if errorlevel 1 goto :fail
    )
)

call :detect_python
if errorlevel 1 (
    echo [ERROR] Python не найден даже после установки.
    goto :fail
)

echo [OK] Python: %PYTHON_CMD%
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Создаю виртуальное окружение .venv
    call :run_py -m venv .venv
    if errorlevel 1 goto :fail
)

set "VENV_PY=.venv\Scripts\python.exe"

echo [INFO] Обновляю pip/setuptools/wheel
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail

if exist "requirements.txt" (
    echo [INFO] Устанавливаю базовые зависимости requirements.txt
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :fail
) else (
    echo [WARN] Файл requirements.txt не найден.
)

if exist "requirements-optional.txt" (
    echo [INFO] Устанавливаю optional зависимости requirements-optional.txt
    "%VENV_PY%" -m pip install -r requirements-optional.txt
    if errorlevel 1 goto :fail
)

echo [INFO] Проверяю голосовые пакеты (SpeechRecognition + PyAudio)
"%VENV_PY%" -m pip install SpeechRecognition
if errorlevel 1 goto :fail

"%VENV_PY%" -m pip install PyAudio
if errorlevel 1 (
    echo [WARN] PyAudio не установился через pip. Пробую pipwin...
    "%VENV_PY%" -m pip install pipwin
    if errorlevel 1 goto :fail
    "%VENV_PY%" -m pipwin install pyaudio
    if errorlevel 1 goto :fail
)

echo.
echo [OK] Установка завершена.
echo [INFO] Далее:
echo        1) copy .env.example .env   (или создай .env вручную)
echo        2) .venv\Scripts\activate
echo        3) python genesis.py
echo        4) python main.py
echo.
goto :done

:detect_python
set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    exit /b 0
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    exit /b 0
)

if exist "%ProgramFiles%\Python311\python.exe" (
    set "PYTHON_CMD=%ProgramFiles%\Python311\python.exe"
    exit /b 0
)

exit /b 1

:run_py
if /I "%PYTHON_CMD%"=="py -3" (
    py -3 %*
    exit /b %errorlevel%
)

"%PYTHON_CMD%" %*
exit /b %errorlevel%

:install_python_winget
where winget >nul 2>&1
if errorlevel 1 exit /b 1

winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements --silent
exit /b %errorlevel%

:install_python_fallback
powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe'; $out=Join-Path $env:TEMP 'python-3.11.9-amd64.exe'; Invoke-WebRequest -Uri $url -OutFile $out; Start-Process -FilePath $out -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0' -Wait"
exit /b %errorlevel%

:fail
echo.
echo [FAIL] Установка завершилась с ошибкой. Проверь вывод выше.
exit /b 1

:done
endlocal
exit /b 0
