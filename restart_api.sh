#!/usr/bin/env bash
# Clean API restart: free port 8000 (no pattern self-match), then relaunch detached.
cd "$(dirname "$0")"
fuser -k 8000/tcp 2>/dev/null
sleep 2
setsid ./run_api.sh > logs/api.log 2>&1 < /dev/null &
echo "API restarting on :8000"
