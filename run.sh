#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if ! command -v python3 &>/dev/null; then
    echo "Ошибка: python3 не найден. Установите Python 3.8+."
    exit 1
fi

if [ ! -d venv ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
fi

source venv/bin/activate

pip install -q -r requirements.txt

python3 run.py