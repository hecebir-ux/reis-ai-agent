"""Telegram plugin — gerçek bot core.telegram_bot içinde."""
PLUGIN_NAME = "telegram"

def start(agent=None):
    from core.telegram_bot import TelegramBot, make_agent_handler
    import config

    if not getattr(config, "TELEGRAM_BOT_TOKEN", ""):
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN yok"}
    handler = make_agent_handler(agent) if agent else None
    bot = TelegramBot(handler=handler)
    bot.start_background()
    return {"ok": True, "bot": bot}
