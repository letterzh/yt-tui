@echo off
rem Запускает приложение из корня проекта и сам устанавливает нужные пакеты.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

.venv\Scripts\python.exe -m planner
if errorlevel 1 goto :error
exit /b 0

:error
echo Не удалось запустить приложение. Проверьте Python и подключение к интернету.
pause
exit /b 1
