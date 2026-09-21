from __future__ import annotations

import json
from pathlib import Path

import config


class RecoveryStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or (config.MEMORY_DIR / "recovery.json"))

    def save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
