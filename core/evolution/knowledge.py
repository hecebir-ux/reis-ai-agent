from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from database.store import SQLiteStore


class KnowledgeMemory:
    """Problem/solution memory on top of SQLite."""

    def __init__(self, store: SQLiteStore | None = None):
        self.store = store or SQLiteStore()
        self.store.ensure_knowledge_table()

    def lookup(self, problem: str, limit: int = 5) -> list[dict[str, Any]]:
        hits = self.store.search_memory(problem[:120], kind="KNOWLEDGE", limit=limit)
        extra = self.store.search_knowledge(problem, limit=limit)
        seen = set()
        out = []
        for row in extra + hits:
            key = (row.get("problem") or row.get("content") or "")[:80]
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out[:limit]

    def remember(
        self,
        problem: str,
        solution: str,
        source: str = "local",
        project: str = "REIS_AI_AGENT",
        success: bool = True,
    ) -> int:
        return self.store.add_knowledge(
            problem=problem,
            solution=solution,
            source=source,
            project=project,
            success=success,
        )

    def log_event(self, kind: str, payload: dict[str, Any], log_path: Path | None = None) -> None:
        path = Path(log_path or (self.store.path.parent.parent / "logs" / "evolution.jsonl"))
        import config

        path = Path(log_path or (config.LOGS_DIR / "evolution.jsonl"))
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, **payload}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
