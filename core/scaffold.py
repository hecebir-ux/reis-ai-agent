from __future__ import annotations

from pathlib import Path

from tools.filesystem import FileSystemTool


TELEGRAM_BOT_TEMPLATE = '''#!/usr/bin/env python3
"""Telegram müzik botu iskeleti. Token .env içinden okunur."""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("musicbot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


def main() -> None:
    if not TOKEN:
        log.error("TELEGRAM_BOT_TOKEN .env içinde yok. Bot başlatılmadı.")
        print("Token eksik. .env dosyasına TELEGRAM_BOT_TOKEN ekleyin.")
        return
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
    except ImportError:
        print("python-telegram-bot kurulu değil. pip install -r requirements.txt")
        return

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Müzik botu hazır. /play komutu iskelette.")

    async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        q = " ".join(context.args) if context.args else ""
        await update.message.reply_text(f"Çalma kuyruğu (iskelet): {q or 'şarkı adı yok'}")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    log.info("Bot başlıyor")
    app.run_polling()


if __name__ == "__main__":
    main()
'''


def scaffold_python_app(project_dir: str, title: str = "REIS App") -> dict:
    fs = FileSystemTool()
    root = Path(project_dir)
    files = {
        "app.py": (
            f'#!/usr/bin/env python3\n"""{title}"""\n'
            "import logging\n\nlog = logging.getLogger(__name__)\nlogging.basicConfig(level=logging.INFO)\n\n"
            "def add(a: int, b: int) -> int:\n    return a + b\n\n"
            "def main() -> None:\n    print(add(2, 3))\n\n"
            'if __name__ == "__main__":\n    main()\n'
        ),
        "test.py": (
            "from app import add\n\n"
            "def test_add():\n    assert add(2, 3) == 5\n\n"
            'if __name__ == "__main__":\n    test_add()\n    print("TESTS_OK")\n'
        ),
        "requirements.txt": "\n",
        "README.md": f"# {title}\n\nREIS AI MAX tarafından oluşturuldu.\n\n## Çalıştır\n\n```\npython app.py\npython test_app.py\n```\n",
    }
    written = []
    for name, content in files.items():
        r = fs.write_file(str(root / name), content)
        written.append({"file": name, **r})
    return {"success": all(x.get("success") for x in written), "files": written, "path": str(root)}


def scaffold_telegram_music_bot(project_dir: str) -> dict:
    fs = FileSystemTool()
    root = Path(project_dir)
    files = {
        "bot.py": TELEGRAM_BOT_TEMPLATE,
        "requirements.txt": "python-telegram-bot>=21.0\npython-dotenv>=1.0.0\n",
        ".env.example": "TELEGRAM_BOT_TOKEN=\n",
        "README.md": (
            "# Telegram Müzik Botu\n\n"
            "1. `.env.example` dosyasını `.env` olarak kopyala\n"
            "2. TELEGRAM_BOT_TOKEN ekle\n"
            "3. `pip install -r requirements.txt`\n"
            "4. `python bot.py`\n"
        ),
        "test.py": (
            "from pathlib import Path\n\n"
            "def test_files():\n"
            "    assert Path('bot.py').exists()\n"
            "    text = Path('bot.py').read_text(encoding='utf-8')\n"
            "    assert 'TELEGRAM_BOT_TOKEN' in text\n"
            "    assert 'TOKEN =' in text\n\n"
            'if __name__ == "__main__":\n    test_files()\n    print("TESTS_OK")\n'
        ),
    }
    written = []
    for name, content in files.items():
        r = fs.write_file(str(root / name), content)
        written.append({"file": name, **r})
    return {"success": all(x.get("success") for x in written), "files": written, "path": str(root)}
