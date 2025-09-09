#!/bin/bash
echo "Running database migrations..."
alembic upgrade head
echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0  --port 8000 --timeout-keep-alive 120 --reload
