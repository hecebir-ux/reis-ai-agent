"""Structured progress events for the REIS Agent Core.

Every long-running agent task emits a stream of AgentEvent objects. UIs
(Telegram, web console, CLI) subscribe to render live progress instead of a
raw traceback dump. The event vocabulary mirrors the canonical agent loop:

    UNDERSTAND -> INTENT -> PLAN -> EXECUTE -> TEST -> HEAL -> VERIFY -> REPORT
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Canonical loop phases (kept as plain strings so they serialise cleanly).
UNDERSTAND = "understand"
INTENT = "intent"
CONTEXT = "context"
MEMORY = "memory"
PLAN = "plan"
RESEARCH = "research"
EXECUTE = "execute"
CODE = "code"
TEST = "test"
DEBUG = "debug"
HEAL = "heal"
SECURITY = "security"
CHECKPOINT = "checkpoint"
DEPLOY = "deploy"
VERIFY = "verify"
REPORT = "report"
CHAT = "chat"
ERROR = "error"
APPROVAL = "approval"

# Human-facing labels + emojis, used by the Telegram/console renderers.
PHASE_LABELS: dict[str, str] = {
    UNDERSTAND: "🧠 Anlıyorum",
    INTENT: "🎯 Niyet belirlendi",
    CONTEXT: "📚 Bağlam toplanıyor",
    MEMORY: "💾 Hafıza",
    PLAN: "🗺️ Planlanıyor",
    RESEARCH: "🔎 Araştırılıyor",
    EXECUTE: "💻 Uygulanıyor",
    CODE: "✍️ Kodlanıyor",
    TEST: "🧪 Test ediliyor",
    DEBUG: "🔧 Hata ayıklanıyor",
    HEAL: "🩹 Onarılıyor",
    SECURITY: "🛡️ Güvenlik kontrolü",
    CHECKPOINT: "📌 Checkpoint",
    DEPLOY: "🚀 Deploy ediliyor",
    VERIFY: "✔️ Doğrulanıyor",
    REPORT: "✅ Tamamlandı",
    CHAT: "💬 Sohbet",
    ERROR: "❌ Hata",
    APPROVAL: "⏸️ Onay bekleniyor",
}


@dataclass
class AgentEvent:
    """A single progress signal from the agent loop."""

    phase: str
    message: str = ""
    level: str = "info"  # info | warn | error | success
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    @property
    def label(self) -> str:
        return PHASE_LABELS.get(self.phase, self.phase)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "label": self.label,
            "message": self.message,
            "level": self.level,
            "data": self.data,
            "ts": self.ts,
        }


# An event sink is any callable that accepts an AgentEvent.
EventSink = Callable[[AgentEvent], None]


class EventBus:
    """Collects events and forwards them to an optional live sink.

    Keeps the full history so a task can be summarised or replayed (e.g. the
    Telegram [LOGLAR] button) after it finishes.
    """

    def __init__(self, sink: Optional[EventSink] = None):
        self._sink = sink
        self.history: list[AgentEvent] = []

    def emit(
        self,
        phase: str,
        message: str = "",
        level: str = "info",
        **data: Any,
    ) -> AgentEvent:
        event = AgentEvent(phase=phase, message=message, level=level, data=dict(data))
        self.history.append(event)
        if self._sink is not None:
            try:
                self._sink(event)
            except Exception:
                # A broken UI sink must never crash the agent loop.
                pass
        return event

    def phases_seen(self) -> list[str]:
        seen: list[str] = []
        for e in self.history:
            if e.phase not in seen:
                seen.append(e.phase)
        return seen

    def transcript(self, limit: int = 40) -> str:
        lines = [f"{e.label}: {e.message}" if e.message else e.label for e in self.history[-limit:]]
        return "\n".join(lines)
