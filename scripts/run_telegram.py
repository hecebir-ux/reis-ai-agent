#!/usr/bin/env python3
"""Run REIS AI on Telegram, powered by the REIS Agent Core bridge.

Natural chat stays conversational; real engineering requests run through the
autonomous loop and stream progress by editing a single message.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.chdir(str(BASE))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from dotenv import load_dotenv

load_dotenv(BASE / ".env", override=True)

import config
from core.agent.loop import ReisMaxAgent
from core.agent_core.core import ReisAgentCore
from core.agent_core.telegram_runtime import build_bridge
from core.evolution.boot import boot_all
from core.llm_client import OllamaClient
from core.telegram_bot import TelegramBot, make_agent_handler

BOT_COMMANDS = [
    {"command": "start", "description": "Başlat"},
    {"command": "help", "description": "Yardım / komutlar"},
    {"command": "status", "description": "Sistem durumu"},
    {"command": "diagnose", "description": "Kendini tara"},
    {"command": "evolve", "description": "Kendini geliştir"},
]


def main() -> int:
    token = (os.getenv("TELEGRAM_BOT_TOKEN", "") or getattr(config, "TELEGRAM_BOT_TOKEN", "")).strip()
    if not token or ":" not in token:
        print("TELEGRAM_BOT_TOKEN eksik. .env veya Secrets içine ekle.")
        return 1

    print("REIS AI Telegram — başlatılıyor…")
    llm = OllamaClient()
    agent = ReisMaxAgent(llm)
    boot = boot_all(llm=llm, agent=agent)
    agent._boot_status = boot  # type: ignore[attr-defined]
    print(f"Self-Evolution: {boot.get('active_count')}/{boot.get('total_count')} aktif")

    core = ReisAgentCore(agent=agent)
    bot = TelegramBot(token=token, handler=make_agent_handler(agent))
    bot.bridge = build_bridge(bot, core)

    bot.api_call("setMyCommands", commands=BOT_COMMANDS)
    me = bot.get_me()
    if me.get("ok"):
        print(f"Bot aktif: @{(me.get('result') or {}).get('username')}")
    else:
        print(f"getMe hatası: {me.get('description')}")
        return 1

    try:
        bot.run_forever()
    except KeyboardInterrupt:
        bot.stop()
        print("\nBot durduruldu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
