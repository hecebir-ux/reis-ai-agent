from __future__ import annotations

from collections import deque
from typing import Any


class ContextEngine:
    def __init__(self, max_messages: int = 16):
        self.messages: deque[dict[str, str]] = deque(maxlen=max_messages)
        self.active_task: dict[str, Any] | None = None
        self.active_project: str | None = None
        self.decisions: deque[str] = deque(maxlen=12)
        self.preferences: dict[str, Any] = {}
        self.open_tasks: list[str] = []

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content[:2000]})

    def set_project(self, path: str | None) -> None:
        self.active_project = path

    def set_task(self, task: dict[str, Any] | None) -> None:
        self.active_task = task

    def remember_decision(self, text: str) -> None:
        self.decisions.append(text[:400])

    def compact(self) -> str:
        parts = []
        if self.active_project:
            parts.append(f"Aktif proje: {self.active_project}")
        if self.active_task:
            parts.append(f"Aktif görev: {self.active_task.get('title', self.active_task.get('id'))}")
        if self.open_tasks:
            parts.append("Açık görevler: " + ", ".join(self.open_tasks[-5:]))
        if self.decisions:
            parts.append("Kararlar: " + " | ".join(list(self.decisions)[-4:]))
        recent = list(self.messages)[-6:]
        if recent:
            hist = "\n".join(f"{m['role']}: {m['content'][:180]}" for m in recent)
            parts.append("Son mesajlar:\n" + hist)
        return "\n".join(parts)[:2500]
