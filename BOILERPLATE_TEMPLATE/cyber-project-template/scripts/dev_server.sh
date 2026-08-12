#!/bin/bash
# Development server launcher for Cyber Project Template

set -e

echo "[Dev Server] Starting Cyber Project Template..."
echo "[Dev Server] Visit http://localhost:8000"

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "[Dev Server] Creating .env from .env.example"
    cp .env.example .env
    echo "[Dev Server] ⚠️  Please edit .env with your Gemini API key, then restart"
fi

# Run FastAPI with auto-reload
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
