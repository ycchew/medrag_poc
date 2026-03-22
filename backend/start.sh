#!/bin/sh
# Startup script for Railway deployment
# Reads PORT from environment and starts uvicorn

PORT=${PORT:-8000}
echo "Starting uvicorn on port $PORT"
uvicorn main:app --host 0.0.0.0 --port "$PORT"
