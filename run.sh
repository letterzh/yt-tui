#!/usr/bin/env bash
# Запускает приложение из корня проекта и сам устанавливает нужные пакеты.
set -eu

cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv .venv
    elif command -v python >/dev/null 2>&1; then
        python -m venv .venv
    else
        echo "Python 3 не найден. Установите Python 3.11 или новее и повторите запуск."
        exit 1
    fi
fi

.venv/bin/python -m pip install -r requirements.txt
exec .venv/bin/python -m planner
