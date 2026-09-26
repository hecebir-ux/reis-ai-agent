#!/usr/bin/env bash
# Cloud Agent start script for REIS AI.
# Ensures the Ollama server is running on every boot (systemd is not available
# in the container, so the daemon must be launched here). Idempotent.
set -euo pipefail

OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"

if curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  echo "[start] Ollama already running at $OLLAMA_URL"
  exit 0
fi

echo "[start] launching ollama serve"
nohup ollama serve >/tmp/ollama_serve.log 2>&1 &

for _ in $(seq 1 30); do
  if curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    echo "[start] Ollama API ready"
    exit 0
  fi
  sleep 1
done

echo "[start] WARNING: Ollama API not ready after 30s (see /tmp/ollama_serve.log)" >&2
exit 0
