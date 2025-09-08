#!/bin/bash
echo "Running database migrations..."
alembic upgrade head
echo "Starting application..."
exec uvicorn api:app --host 0.0.0.0 --port 8080 --timeout-keep-alive 120
