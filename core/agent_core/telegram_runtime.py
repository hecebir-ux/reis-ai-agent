"""Telegram runtime bridge for the REIS Agent Core.

Turns the raw "one message in, one message out" bot into a real agent UX:

  * Natural chat stays conversational (single reply).
  * Real engineering tasks run in the background and stream progress by
    editing ONE Telegram message (🔎 → 💻 → 🧪 → ✔️ → ✅) instead of dumping
    raw tracebacks.

The bridge is transport-agnostic: it depends only on `send`/`edit` callables,
so it can be unit-tested with a fake transport and wired to the real Telegram
Bot API in production.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from core.agent_core.core import MODE_CHAT, ReisAgentCore
from core.agent_core.events import AgentEvent, REPORT

# Transport callables:
#   send(chat_id, text) -> message_id
#   edit(chat_id, message_id, text) -> None
SendFn = Callable[[int, str], Any]
EditFn = Callable[[int, int, str], Any]


class ProgressRenderer:
    """Accumulates events into a single, human-readable progress board."""

    def __init__(self, header: str = "🤖 REIS AI çalışıyor"):
        self.header = header
        self._order: list[str] = []
        self._lines: dict[str, str] = {}

    def update(self, event: AgentEvent) -> str:
        # One line per phase; later events for the same phase overwrite it.
        line = event.label
        if event.message:
            line = f"{event.label}: {event.message}"
        if event.phase not in self._lines:
            self._order.append(event.phase)
        self._lines[event.phase] = line
        return self.render()

    def render(self) -> str:
        body = "\n".join(self._lines[p] for p in self._order)
        return f"{self.header}\n\n{body}" if body else self.header


class TelegramAgentBridge:
    """Routes an incoming Telegram message to chat or a live agent task."""

    def __init__(
        self,
        core: ReisAgentCore,
        send: SendFn,
        edit: EditFn,
        run_async: bool = True,
    ):
        self.core = core
        self.send = send
        self.edit = edit
        self.run_async = run_async

    def handle(self, chat_id: int, text: str) -> Optional[threading.Thread]:
        mode = self.core.classify_mode(text)
        print(f"[REIS][telegram] chat={chat_id} mode={mode} text={text!r}", flush=True)
        if mode == MODE_CHAT:
            result = self.core.run(text)
            self.send(chat_id, result.get("message") or "(boş yanıt)")
            print(f"[REIS][telegram] chat={chat_id} chat-reply gönderildi", flush=True)
            return None
        return self._run_task(chat_id, text)

    def _run_task(self, chat_id: int, text: str) -> Optional[threading.Thread]:
        renderer = ProgressRenderer()
        message_id = self.send(chat_id, f"{renderer.header}\n\n🧠 Anlıyorum…")
        last_rendered = {"text": ""}

        def on_event(event: AgentEvent) -> None:
            rendered = renderer.update(event)
            # Avoid redundant edits (Telegram rejects identical content).
            if rendered != last_rendered["text"]:
                last_rendered["text"] = rendered
                try:
                    self.edit(chat_id, message_id, rendered)
                except Exception:
                    pass

        def work() -> dict[str, Any]:
            result = self.core.run(text, on_event=on_event)
            # Final detailed report as a follow-up message.
            final = result.get("message")
            if final:
                try:
                    self.send(chat_id, final)
                except Exception:
                    pass
            print(
                f"[REIS][telegram] chat={chat_id} görev bitti ok={result.get('ok')} "
                f"mode={result.get('mode')}",
                flush=True,
            )
            return result

        if self.run_async:
            thread = threading.Thread(target=work, name=f"reis-task-{chat_id}", daemon=True)
            thread.start()
            return thread
        work()
        return None


def build_bridge(bot: Any, core: ReisAgentCore, run_async: bool = True) -> TelegramAgentBridge:
    """Wire a bridge to a live TelegramBot instance."""

    def send(chat_id: int, text: str) -> Optional[int]:
        resp = bot.send_message(chat_id, text)
        return ((resp or {}).get("result") or {}).get("message_id")

    def edit(chat_id: int, message_id: Optional[int], text: str) -> None:
        if message_id is None:
            bot.send_message(chat_id, text)
        else:
            bot.edit_message(chat_id, message_id, text)

    return TelegramAgentBridge(core, send, edit, run_async=run_async)
