@echo off
chcp 65001 >nul

REM Проверка зависимостей
pip show customtkinter >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r "%~dp0requirements.txt"
    echo Done.
    pause
)

REM Запуск скрипта
start "" pythonw.exe "%~dp0a.py"
exit
