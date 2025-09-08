#!/bin/bash
echo "Running database migrations..."
alembic upgrade head
echo "Starting application..."
exec uvicorn main:app --host 0.0.0.0 --port 8080 --reload --timeout-keep-alive 120
