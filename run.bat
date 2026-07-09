@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Ошибка: python не найден. Установите Python 3.8+.
    pause
    exit /b 1
)

if not exist venv (
    echo Создание виртуального окружения...
    python -m venv venv
)

call venv\Scripts\activate.bat

pip install -q -r requirements.txt

python run.py
pause