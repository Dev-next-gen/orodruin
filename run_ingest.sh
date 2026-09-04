#!/usr/bin/env bash
cd "$(dirname "$0")/backend"
. .venv/bin/activate
exec python -m app.ingest.run --loop 900
