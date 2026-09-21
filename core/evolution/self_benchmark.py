from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Callable

from core.metrics import metrics


class SelfBenchmark:
    def measure(self, fn: Callable[[], Any], rounds: int = 1) -> dict[str, Any]:
        times: list[float] = []
        last = None
        err = None
        for _ in range(max(1, rounds)):
            t0 = time.perf_counter()
            try:
                last = fn()
            except Exception as e:
                err = str(e)
                last = None
            times.append(time.perf_counter() - t0)
        avg = sum(times) / len(times)
        return {
            "ok": err is None,
            "avg_s": round(avg, 4),
            "min_s": round(min(times), 4),
            "max_s": round(max(times), 4),
            "error": err,
            "value": last if not isinstance(last, (bytes,)) else None,
        }

    def compare(self, old: dict[str, Any], new: dict[str, Any], max_regression: float = 1.08) -> dict[str, Any]:
        old_t = float(old.get("avg_s") or 0)
        new_t = float(new.get("avg_s") or 0)
        better = new.get("ok") and (old_t == 0 or new_t <= old_t * max_regression) and new_t <= old_t if old_t else new.get("ok")
        if old_t > 0:
            better = bool(new.get("ok")) and new_t <= old_t * max_regression and new_t < old_t
            # accept equal-or-better within 2% noise as accept if also ok
            accept = bool(new.get("ok")) and new_t <= old_t * max_regression
        else:
            accept = bool(new.get("ok"))
        return {
            "accept": accept and bool(new.get("ok")),
            "improved": bool(old_t and new_t and new_t < old_t),
            "old_s": old_t,
            "new_s": new_t,
            "delta_s": round(new_t - old_t, 4),
        }


@contextmanager
def timed(name: str):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        metrics.record_tool(name, time.perf_counter() - t0)
