#!/usr/bin/env python3
"""Canlı duman testi: Ollama + sohbet + slash komutlar."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.chdir(str(HERE))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from core.agent.loop import ReisMaxAgent
from core.commands import parse_command
from core.llm_client import OllamaClient
from main import handle_slash


def main() -> int:
    llm = OllamaClient()
    h = llm.health_check()
    print("OLLAMA", h.get("ok"), h.get("models"))
    if not h.get("ok"):
        print("FAIL: ollama yok")
        return 1
    agent = ReisMaxAgent(llm)
    handle_slash(agent, "/status", "")
    print("--- sohbet ---")
    result = agent.handle("selam kısaca kimsin")
    print("KIND", result.get("kind"), "OK", result.get("ok"), "LEN", len(result.get("message") or ""))
    msg = result.get("message") or ""
    if not msg or msg.startswith("[LLM_HATA"):
        print("FAIL chat", msg[:300])
        return 1
    print("PASS chat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
