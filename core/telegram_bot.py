"""REIS AI Telegram bot — long polling, token only from env."""
from __future__ import annotations

import json
import time
import threading
from typing import Any, Callable

import requests

import config


class TelegramBot:
    """Local Ollama agent bridge over Telegram Bot API (no third-party bot lib)."""

    def __init__(
        self,
        token: str | None = None,
        handler: Callable[[str, dict[str, Any]], str] | None = None,
        allowed_ids: set[int] | None = None,
    ):
        self.token = (token or getattr(config, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        self.api = f"https://api.telegram.org/bot{self.token}"
        self.handler = handler
        self.allowed_ids = allowed_ids if allowed_ids is not None else _parse_allowed()
        self.offset = 0
        self._stop = threading.Event()
        self.session = requests.Session()
        self.timeout = int(getattr(config, "TELEGRAM_TIMEOUT", 60))

    @property
    def configured(self) -> bool:
        return bool(self.token) and ":" in self.token

    def api_call(self, method: str, **params: Any) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN yok"}
        try:
            r = self.session.post(
                f"{self.api}/{method}",
                json=params or None,
                timeout=self.timeout + 10,
            )
            data = r.json()
            return data if isinstance(data, dict) else {"ok": False, "error": "bad json"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def get_me(self) -> dict[str, Any]:
        return self.api_call("getMe")

    def send_message(self, chat_id: int, text: str, parse_mode: str | None = None) -> dict[str, Any]:
        text = (text or "")[:4000] or "(boş yanıt)"
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self.api_call("sendMessage", **payload)

    def _allowed(self, user_id: int | None) -> bool:
        if not self.allowed_ids:
            return True
        return user_id is not None and int(user_id) in self.allowed_ids

    def handle_update(self, update: dict[str, Any]) -> dict[str, Any]:
        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat") or {}
        user = msg.get("from") or {}
        chat_id = chat.get("id")
        user_id = user.get("id")
        text = (msg.get("text") or "").strip()
        if chat_id is None:
            return {"ok": False, "reason": "no_chat"}
        if not self._allowed(user_id):
            self.send_message(chat_id, "Yetkin yok. TELEGRAM_ALLOWED_IDS ile izin ver.")
            return {"ok": False, "reason": "forbidden"}
        if not text:
            return {"ok": True, "skipped": True}

        low = text.lower()
        if low in {"/start", "start"}:
            reply = (
                "REIS AI hazır.\n"
                "Komutlar:\n"
                "/evolve — kendini geliştir\n"
                "/diagnose — kodunu tara\n"
                "/status — durum\n"
                "/help — yardım\n\n"
                "Veya doğal dil yaz (örn. Kendini analiz et.)"
            )
            self.send_message(chat_id, reply)
            return {"ok": True, "kind": "start"}
        if low in {"/help", "help", "/yardim", "/yardım"}:
            self.send_message(
                chat_id,
                "REIS AI Telegram.\n"
                "• Yazılım / sohbet / self-evolution\n"
                "• /evolve /diagnose /status\n"
                "Token asla sohbete yazma.",
            )
            return {"ok": True, "kind": "help"}
        if low.startswith("/status"):
            if self.handler:
                reply = self.handler("/status", {"chat_id": chat_id, "user_id": user_id})
            else:
                reply = "Status handler yok."
            self.send_message(chat_id, reply)
            return {"ok": True, "kind": "status"}
        if low.startswith("/evolve"):
            text = "Kendini analiz et, eksiklerini bul ve geliştir."
        elif low.startswith("/diagnose"):
            text = "Kendini analiz et."

        self.send_message(chat_id, "İşleniyor…")
        try:
            if self.handler:
                reply = self.handler(text, {"chat_id": chat_id, "user_id": user_id})
            else:
                reply = f"Echo: {text}"
        except Exception as e:
            reply = f"Hata: {type(e).__name__}: {e}"
        self.send_message(chat_id, reply)
        return {"ok": True, "kind": "message"}

    def poll_once(self) -> list[dict[str, Any]]:
        data = self.api_call(
            "getUpdates",
            offset=self.offset,
            timeout=min(50, self.timeout),
            allowed_updates=["message", "edited_message"],
        )
        if not data.get("ok"):
            return []
        results = []
        for upd in data.get("result") or []:
            self.offset = max(self.offset, int(upd.get("update_id", 0)) + 1)
            results.append(self.handle_update(upd))
        return results

    def run_forever(self) -> None:
        if not self.configured:
            raise RuntimeError("TELEGRAM_BOT_TOKEN .env içinde tanımlı değil.")
        me = self.get_me()
        if not me.get("ok"):
            raise RuntimeError(f"Telegram API: {me.get('error') or me.get('description')}")
        uname = (me.get("result") or {}).get("username")
        print(f"[Telegram] Bot aktif: @{uname}")
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception as e:
                print(f"[Telegram] poll hata: {e}")
                time.sleep(3)

    def stop(self) -> None:
        self._stop.set()

    def start_background(self) -> threading.Thread:
        t = threading.Thread(target=self.run_forever, name="reis-telegram", daemon=True)
        t.start()
        return t


def _parse_allowed() -> set[int]:
    raw = (getattr(config, "TELEGRAM_ALLOWED_IDS", "") or "").strip()
    out: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            out.add(int(part))
    return out


def make_agent_handler(agent) -> Callable[[str, dict[str, Any]], str]:
    def _handle(text: str, meta: dict[str, Any]) -> str:
        t = (text or "").strip()
        if t.lower() in {"/status", "status"}:
            from core.metrics import metrics

            h = agent.llm.health_check()
            snap = metrics.snapshot()
            boot = getattr(agent, "_boot_status", None) or {}
            return (
                f"Ollama: {'OK' if h.get('ok') else 'HATA'}\n"
                f"Sohbet: {agent.llm.chat_model}\n"
                f"Kod: {agent.llm.model}\n"
                f"Evolution: {boot.get('active_count', '?')}/{boot.get('total_count', '?')}\n"
                f"CPU/RAM: {snap.get('cpu')}/{snap.get('ram')}"
            )
        out = agent.handle(t)
        return (out.get("message") or json.dumps(out, ensure_ascii=False)[:1500])[:4000]

    return _handle
