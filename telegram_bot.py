#!/usr/bin/env python3
"""REIS AI Telegram bot giriş noktası."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.chdir(str(BASE))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from dotenv import load_dotenv

load_dotenv(BASE / ".env")

import config
from core.agent.loop import ReisMaxAgent
from core.evolution.boot import boot_all
from core.llm_client import OllamaClient
from core.telegram_bot import TelegramBot, make_agent_handler


def main() -> int:
    token = getattr(config, "TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("TELEGRAM_BOT_TOKEN eksik.")
        print("1) @BotFather ile bot oluştur")
        print("2) .env dosyasına ekle: TELEGRAM_BOT_TOKEN=123:ABC...")
        print("3) İsteğe bağlı: TELEGRAM_ALLOWED_IDS=senin_telegram_id")
        return 1

    llm = OllamaClient()
    agent = ReisMaxAgent(llm)
    boot = boot_all(llm=llm, agent=agent)
    agent._boot_status = boot  # type: ignore[attr-defined]
    print(f"Self-Evolution: {boot.get('active_count')}/{boot.get('total_count')} aktif")

    bot = TelegramBot(token=token, handler=make_agent_handler(agent))
    try:
        bot.run_forever()
    except KeyboardInterrupt:
        bot.stop()
        print("\nBot durdu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
