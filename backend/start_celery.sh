#!/bin/bash
cd "$(dirname "$0")" || exit

if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment 'venv' not found."
    exit 1
fi

echo "Starting Celery Worker..."
celery -A core worker --loglevel=INFO
