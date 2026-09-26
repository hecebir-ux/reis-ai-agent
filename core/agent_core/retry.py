"""Autonomous retry engine.

When an action fails, REIS AI does not immediately give up. It retries the same
method (with exponential backoff), then falls back to alternative strategies,
until it succeeds or a bounded budget is exhausted. No infinite retries.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class RetryPolicy:
    max_attempts: int = 2          # attempts per strategy
    base_delay: float = 0.5        # seconds
    max_delay: float = 8.0
    backoff: float = 2.0

    def delay_for(self, attempt_index: int) -> float:
        return min(self.max_delay, self.base_delay * (self.backoff ** attempt_index))


@dataclass
class Attempt:
    index: int
    strategy: str
    ok: bool
    error: str = ""
    result: Any = None


def is_ok(result: Any) -> bool:
    """A result is successful if it is truthy / has ok|success True."""
    if isinstance(result, dict):
        if "ok" in result:
            return bool(result["ok"])
        if "success" in result:
            return bool(result["success"])
        return True
    return bool(result)


# A strategy is either a callable or a (name, callable) pair.
Strategy = Any
OnAttempt = Optional[Callable[[Attempt], None]]


class RetryEngine:
    def __init__(self, policy: Optional[RetryPolicy] = None, sleep: Callable[[float], None] = time.sleep):
        self.policy = policy or RetryPolicy()
        self._sleep = sleep

    @staticmethod
    def _normalize(strategies: list[Strategy]) -> list[tuple[str, Callable[[], Any]]]:
        out: list[tuple[str, Callable[[], Any]]] = []
        for i, s in enumerate(strategies):
            if isinstance(s, tuple):
                out.append((s[0], s[1]))
            else:
                out.append((getattr(s, "__name__", f"strategy_{i}"), s))
        return out

    def run(self, strategies: list[Strategy], on_attempt: OnAttempt = None) -> dict[str, Any]:
        attempts: list[Attempt] = []
        norm = self._normalize(strategies)
        global_index = 0
        last: Optional[Attempt] = None

        for name, fn in norm:
            for a in range(self.policy.max_attempts):
                try:
                    res = fn()
                    ok = is_ok(res)
                    err = "" if ok else "strategy returned failure"
                except Exception as e:  # never propagate; capture and continue
                    res, ok, err = None, False, f"{type(e).__name__}: {e}"
                attempt = Attempt(global_index, name, ok, err, res)
                attempts.append(attempt)
                last = attempt
                global_index += 1
                if on_attempt:
                    try:
                        on_attempt(attempt)
                    except Exception:
                        pass
                if ok:
                    return {
                        "ok": True,
                        "result": res,
                        "strategy": name,
                        "attempts": [a.__dict__ for a in attempts],
                        "attempt_count": len(attempts),
                    }
                # Backoff before the next attempt of the same strategy.
                if a < self.policy.max_attempts - 1:
                    self._sleep(self.policy.delay_for(a))

        return {
            "ok": False,
            "result": last.result if last else None,
            "strategy": last.strategy if last else None,
            "error": last.error if last else "no strategy",
            "attempts": [a.__dict__ for a in attempts],
            "attempt_count": len(attempts),
        }
