#!/usr/bin/env bash
cd "$(dirname "$0")/backend"
. .venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
