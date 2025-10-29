#!/usr/bin/env bash
set -euo pipefail

# Simple entrypoint for the Deep Research Agent container
# Modes:
#   server - start the FastAPI app with uvicorn
#   cli    - start an interactive CLI to ask questions
#   webui  - start the lightweight web UI server

MODE=${1:-server}

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8081}

case "$MODE" in
  server)
    echo "Starting FastAPI server (uvicorn)..."
    exec uvicorn myai.api:app --host ${HOST} --port ${PORT} --log-level info
    ;;
  cli)
    echo "Starting interactive CLI. Type your question and press enter. Ctrl-D to quit."
    # A minimal loop to ask questions directly to the agent via the bundled helper
    while true; do
      printf "Question: "
      if ! read -r QUESTION; then
        echo
        exit 0
      fi
      python3 - <<PY
from myai.api import test_research_endpoint
import asyncio
print('Running research...')
res = asyncio.run(test_research_endpoint('$QUESTION'))
print('\n--- Report ---')
print(res['report'])
PY
    done
    ;;
  webui)
    echo "Starting web UI (Gunicorn + Flask)..."
    # Run Flask app under Gunicorn with a small number of workers suitable for lightweight containers
    exec gunicorn --bind ${HOST}:${PORT} --workers 2 --threads 4 --log-level info --access-logfile - "webui:app"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac
