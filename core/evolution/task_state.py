from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import config

STATE_PATH = config.MEMORY_DIR / "evolution_state.json"


class EvolutionState:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or STATE_PATH)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, state: dict[str, Any]) -> None:
        state = dict(state)
        state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def start(self, goal: str, steps: list[str]) -> dict[str, Any]:
        state = {
            "task": "self_evolution",
            "goal": goal,
            "steps": steps,
            "completed": [],
            "current": steps[0] if steps else "",
            "results": {},
            "status": "RUNNING",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.save(state)
        return state

    def mark(self, step: str, result: Any = None) -> dict[str, Any]:
        state = self.load() or {}
        done = list(state.get("completed") or [])
        if step not in done:
            done.append(step)
        state["completed"] = done
        results = dict(state.get("results") or {})
        if result is not None:
            results[step] = _clip(result)
        state["results"] = results
        remaining = [s for s in (state.get("steps") or []) if s not in done]
        state["current"] = remaining[0] if remaining else "done"
        if not remaining:
            state["status"] = "COMPLETED"
        self.save(state)
        return state

    def fail(self, step: str, error: str) -> dict[str, Any]:
        state = self.load() or {}
        state["status"] = "FAILED"
        state["current"] = step
        state["error"] = error[:800]
        self.save(state)
        return state

    def unfinished(self) -> dict[str, Any] | None:
        state = self.load()
        if state.get("status") == "RUNNING":
            return state
        return None


def _clip(result: Any) -> Any:
    if isinstance(result, dict):
        out = {}
        for k, v in list(result.items())[:40]:
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[k] = v if not isinstance(v, str) else v[:400]
            elif isinstance(v, list):
                out[k] = v[:12]
            elif isinstance(v, dict):
                out[k] = {ik: iv for ik, iv in list(v.items())[:8]}
            else:
                out[k] = str(v)[:200]
        return out
    return str(result)[:400]
