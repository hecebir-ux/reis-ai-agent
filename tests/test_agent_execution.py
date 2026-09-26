#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REIS Agent Core — execution & autonomy extension tests (deterministic)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.chdir(str(HERE))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    ok = bool(cond)
    print(("[OK] " if ok else "[HATA] ") + name + (f" — {detail[:200]}" if detail else ""))
    RESULTS.append((name, ok, detail))
    return ok


def test_retry_engine() -> None:
    from core.agent_core.retry import RetryEngine, RetryPolicy

    slept: list[float] = []
    eng = RetryEngine(RetryPolicy(max_attempts=2, base_delay=0.1), sleep=lambda s: slept.append(s))

    # Primary fails, alternative succeeds.
    out = eng.run([("primary", lambda: {"ok": False}), ("alt", lambda: {"ok": True})])
    check("Retry falls back to alternative", out["ok"] and out["strategy"] == "alt", str(out.get("strategy")))

    # Same strategy retried: fails once then succeeds -> one backoff sleep.
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        return {"ok": state["n"] >= 2}

    slept.clear()
    out2 = eng.run([("flaky", flaky)])
    check("Retry same strategy until success", out2["ok"], f"attempts={out2['attempt_count']}")
    check("Retry used exponential backoff sleep", len(slept) == 1, f"slept={slept}")

    # Exception inside a strategy is captured, not raised.
    def boom():
        raise ValueError("patla")

    out3 = eng.run([("boom", boom), ("safe", lambda: {"ok": True})])
    check("Retry captures exceptions and continues", out3["ok"] and out3["strategy"] == "safe")

    # Bounded: all fail -> ok False, no infinite loop.
    # 2 strategies x max_attempts(2) = 4 bounded attempts.
    out4 = eng.run([("a", lambda: {"ok": False}), ("b", lambda: {"ok": False})])
    check("Retry is bounded (no infinite loop)", not out4["ok"] and out4["attempt_count"] == 4,
          f"attempts={out4['attempt_count']}")


def test_error_memory() -> None:
    from core.agent_core.error_memory import ErrorMemory
    from database.store import SQLiteStore

    dbpath = Path(tempfile.gettempdir()) / "reis_errmem_test.db"
    dbpath.unlink(missing_ok=True)
    store = SQLiteStore(dbpath)
    em = ErrorMemory(store)

    err_a = "Traceback (most recent call last):\n  File 'x.py', line 3\nZeroDivisionError: division by zero"
    err_a2 = "Traceback (most recent call last):\n  File 'y.py', line 99\nZeroDivisionError: division by zero"
    err_b = "NameError: name 'foo' is not defined"

    check("Signature stable across volatile paths/lines", em.signature(err_a) == em.signature(err_a2),
          f"{em.signature(err_a)} vs {em.signature(err_a2)}")
    check("Different errors -> different signature", em.signature(err_a) != em.signature(err_b))

    em.record(err_a, fix="guard against zero divisor", success=True)
    check("Successful fix retrievable", em.successful_fix(err_a2) is not None, em.successful_fix(err_a2) or "")

    em.record(err_b, fix="define foo before use", success=False)
    check("Failed fix is flagged", em.has_failed_fix(err_b, "define foo before use"))
    check("Unknown fix not flagged", not em.has_failed_fix(err_b, "some other fix"))
    dbpath.unlink(missing_ok=True)


def test_task_ledger_and_gate() -> None:
    from core.agent_core.tasks import (
        STATUS_COMPLETED,
        STATUS_FAILED,
        TaskLedger,
        evaluate_gate,
    )
    from database.store import SQLiteStore

    # Gate logic
    st, failed = evaluate_gate({"execution": True, "tests": True, "verification": True})
    check("Gate: all critical pass -> COMPLETED", st == STATUS_COMPLETED, st)
    st, failed = evaluate_gate({"execution": True, "tests": True, "verification": False})
    check("Gate: unverified -> FAILED", st == STATUS_FAILED and "verification" in failed, str(failed))
    st, failed = evaluate_gate({"execution": False})
    check("Gate: no execution -> FAILED", st == STATUS_FAILED, st)

    dbpath = Path(tempfile.gettempdir()) / "reis_ledger_test.db"
    dbpath.unlink(missing_ok=True)
    ledger = TaskLedger(SQLiteStore(dbpath))

    tid = ledger.open("bir uygulama oluştur", intent="CODING", mode="agent")
    check("Ledger opens a task id", tid.startswith("task_"), tid)
    ledger.log(tid, "plan", "planlanıyor")
    ledger.log(tid, "execute", "adım 1")
    ledger.set_retry(tid, 1)

    gate = ledger.finalize(
        tid,
        {"execution": True, "tests": True, "verification": True, "health": True},
        {"reason": "ok"},
        message="tamam",
    )
    check("Ledger finalize -> COMPLETED", gate["status"] == STATUS_COMPLETED, gate["status"])
    stored = ledger.get(tid)
    check("Ledger persists status", stored and stored["status"] == STATUS_COMPLETED)
    txt = ledger.status_text(tid)
    check("Status text renders task + gate", tid in txt and "Kapı" in txt, txt.replace("\n", " | ")[:120])

    # A failed task
    tid2 = ledger.open("başka görev", intent="CODING", mode="agent")
    gate2 = ledger.finalize(tid2, {"execution": True, "tests": False, "verification": False}, {"reason": "test yok"})
    check("Ledger finalize -> FAILED when unverified", gate2["status"] == STATUS_FAILED, gate2["status"])
    check("Latest returns most recent task", ledger.latest()["id"] == tid2)
    dbpath.unlink(missing_ok=True)


def test_status_routing_and_preflight() -> None:
    from core.agent_core.core import MODE_STATUS, ReisAgentCore

    core = ReisAgentCore()
    for text in ("görev ne durumda?", "task_abc123 durumu", "son görev"):
        check(f"Status route: '{text}'", core.classify_mode(text) == MODE_STATUS, core.classify_mode(text))

    # Healthy environment -> no capability gaps blocking agent tasks.
    from core.agent_core.events import EventBus

    gap = core.preflight(EventBus())
    check("Preflight: no critical capability gap in this env", gap == [], str(gap))


def main() -> int:
    print("=" * 70)
    print("  REIS AGENT — EXECUTION & AUTONOMY TESTLERİ")
    print("=" * 70)
    test_retry_engine()
    test_error_memory()
    test_task_ledger_and_gate()
    test_status_routing_and_preflight()
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n  SONUÇ: {passed}/{total}")
    ok = passed == total
    print("  EXECUTION & AUTONOMY READY" if ok else "  BAŞARISIZ TEST VAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
