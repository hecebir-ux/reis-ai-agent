#!/usr/bin/env python3
"""REIS AI — Windows uygulama giriş noktası (UI + Telegram + Self-Evolution)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = _app_root()
RUNTIME = _runtime_root()
sys.path.insert(0, str(ROOT))
os.chdir(str(RUNTIME))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _prepare_config():
    import config

    config.BASE_DIR = RUNTIME
    for name, folder in (
        ("WORKSPACE_DIR", "workspace"),
        ("MEMORY_DIR", "memory"),
        ("LOGS_DIR", "logs"),
        ("DATABASE_DIR", "database"),
        ("PLUGINS_DIR", "plugins"),
        ("PROJECTS_DIR", "projects"),
        ("BACKUPS_DIR", "backups"),
        ("CACHE_DIR", "cache"),
    ):
        p = RUNTIME / folder
        p.mkdir(parents=True, exist_ok=True)
        setattr(config, name, p)
    config.MEMORY_FILE = config.MEMORY_DIR / "sessions.json"
    config.SQLITE_PATH = config.DATABASE_DIR / "reis_max.db"
    config.SAFE_ROOTS = [str(config.WORKSPACE_DIR), str(RUNTIME)]
    try:
        from dotenv import load_dotenv

        load_dotenv(RUNTIME / ".env", override=True)
        # re-read telegram after dotenv
        config.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", getattr(config, "TELEGRAM_BOT_TOKEN", ""))
        config.TELEGRAM_ALLOWED_IDS = os.getenv("TELEGRAM_ALLOWED_IDS", getattr(config, "TELEGRAM_ALLOWED_IDS", ""))
    except Exception:
        pass
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="REIS AI App")
    parser.add_argument("--ui", action="store_true", help="Web arayüzü")
    parser.add_argument("--telegram", action="store_true", help="Sadece Telegram bot")
    parser.add_argument("--both", action="store_true", help="UI + Telegram birlikte")
    parser.add_argument("--no-browser", action="store_true")
    args, _ = parser.parse_known_args()

    config = _prepare_config()
    from colorama import Fore, Style, init

    init()
    print(f"{Fore.CYAN}REIS AI{Style.RESET_ALL} uygulama başlatılıyor...")
    print(f"  Veri: {RUNTIME}")

    from core.agent.loop import ReisMaxAgent
    from core.evolution.boot import boot_all, format_boot_report
    from core.llm_client import OllamaClient
    from core.telegram_bot import TelegramBot, make_agent_handler

    llm = OllamaClient()
    h = llm.health_check()
    if not h.get("ok"):
        print(f"{Fore.YELLOW}Uyarı: Ollama — {h.get('error')}{Style.RESET_ALL}")

    agent = ReisMaxAgent(llm)
    boot = boot_all(llm=llm, agent=agent)
    agent._boot_status = boot  # type: ignore[attr-defined]
    print(format_boot_report(boot))

    token = (getattr(config, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    want_tg = args.telegram or args.both or (
        bool(token) and getattr(config, "TELEGRAM_AUTO_START", True) and not args.ui
    )
    # Default (no flags): UI + telegram-if-token
    if not args.ui and not args.telegram and not args.both:
        want_ui = getattr(config, "UI_ENABLED", True)
        want_tg = bool(token) and getattr(config, "TELEGRAM_AUTO_START", True)
    else:
        want_ui = args.ui or args.both or (not args.telegram)

    tg_thread = None
    if want_tg:
        if not token:
            print(f"{Fore.YELLOW}Telegram: TELEGRAM_BOT_TOKEN yok — bot atlandı.{Style.RESET_ALL}")
            print("  .env → TELEGRAM_BOT_TOKEN=...  (BotFather)")
            if args.telegram and not want_ui:
                return 1
        else:
            bot = TelegramBot(token=token, handler=make_agent_handler(agent))
            try:
                from core.agent_core.core import ReisAgentCore
                from core.agent_core.telegram_runtime import build_bridge

                bot.bridge = build_bridge(bot, ReisAgentCore(agent=agent))
            except Exception as _bridge_err:  # keep bot working even if bridge fails
                print(f"Agent Core bridge kurulamadı: {_bridge_err}")
            if args.telegram and not want_ui:
                bot.run_forever()
                return 0
            tg_thread = bot.start_background()
            print(f"{Fore.GREEN}Telegram bot arka planda aktif.{Style.RESET_ALL}")

    if want_ui:
        ui_web = ROOT / "ui" / "web"
        if not ui_web.exists():
            ui_web = RUNTIME / "ui" / "web"
        from ui import app_server

        app_server.WEB_DIR = ui_web
        print(f"  UI: {ui_web}")
        app_server.run_ui(
            host=getattr(config, "UI_HOST", "127.0.0.1"),
            port=int(getattr(config, "UI_PORT", 8765)),
            open_browser=getattr(config, "UI_OPEN_BROWSER", True) and not args.no_browser,
            llm=llm,
        )
    elif tg_thread:
        try:
            tg_thread.join()
        except KeyboardInterrupt:
            print("\nKapatıldı.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nKapatıldı.")
        raise SystemExit(0)
