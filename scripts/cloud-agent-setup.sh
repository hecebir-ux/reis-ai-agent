#!/usr/bin/env bash
# Cloud Agent install script for REIS AI.
# Idempotent: safe to run repeatedly and against a pre-baked snapshot.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OLLAMA_MODEL="${REIS_OLLAMA_MODEL:-llama3.2:1b}"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"

echo "[setup] REIS AI cloud-agent install -> $REPO_ROOT"

# 1. System packages the app assumes (Linux lacks a bare `python`; ollama needs zstd).
missing_pkgs=()
command -v python           >/dev/null 2>&1 || missing_pkgs+=(python-is-python3)
python3 -m venv --help      >/dev/null 2>&1 || missing_pkgs+=(python3-venv)
command -v zstd             >/dev/null 2>&1 || missing_pkgs+=(zstd)
command -v curl             >/dev/null 2>&1 || missing_pkgs+=(curl)
if [ "${#missing_pkgs[@]}" -gt 0 ]; then
  echo "[setup] installing system packages: ${missing_pkgs[*]}"
  sudo apt-get update -qq
  sudo apt-get install -y -qq "${missing_pkgs[@]}"
fi

# 2. Ollama runtime (local LLM backend).
if ! command -v ollama >/dev/null 2>&1; then
  echo "[setup] installing Ollama"
  curl -fsSL https://ollama.com/install.sh | sudo sh
fi

# 3. Python virtualenv + dependencies (idempotent).
if [ ! -x .venv/bin/python ]; then
  echo "[setup] creating .venv"
  python3 -m venv .venv
fi
./.venv/bin/python -m pip install --upgrade pip -q
./.venv/bin/pip install -r requirements.txt -q

# 4. Local .env with a small model wired up (only created if absent).
if [ ! -f .env ]; then
  echo "[setup] writing .env"
  cat > .env <<EOF
OLLAMA_BASE_URL=$OLLAMA_URL
OLLAMA_CHAT_MODEL=$OLLAMA_MODEL
OLLAMA_CODE_MODEL=$OLLAMA_MODEL
OLLAMA_FAST_MODEL=$OLLAMA_MODEL
OLLAMA_RESEARCH_MODEL=$OLLAMA_MODEL
OLLAMA_REASONING_MODEL=$OLLAMA_MODEL
OLLAMA_TIMEOUT=300
UI_ENABLED=true
UI_HOST=127.0.0.1
UI_PORT=8765
UI_OPEN_BROWSER=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_IDS=
TELEGRAM_AUTO_START=true
TELEGRAM_TIMEOUT=60
EOF
fi

# 5. Make sure the model is present (needs the server running to pull).
if ! ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL%%:*}"; then
  echo "[setup] starting a temporary ollama server to pull $OLLAMA_MODEL"
  if ! curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
    nohup ollama serve >/tmp/ollama_serve.log 2>&1 &
    for _ in $(seq 1 30); do
      curl -sf "$OLLAMA_URL/api/tags" >/dev/null 2>&1 && break
      sleep 1
    done
  fi
  ollama pull "$OLLAMA_MODEL"
fi

echo "[setup] done."
