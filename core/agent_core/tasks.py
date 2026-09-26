"""Task Ledger — durable, observable, resumable task records.

Every real agent task gets a persisted record (SQLite) carrying its intent,
live phase, retry count, structured event log and a verification checklist.
This powers:
  * long-running background execution (Telegram returns a task_id immediately),
  * "görev ne durumda?" status queries,
  * the FINAL VERIFICATION GATE (a task only becomes COMPLETED when the
    critical checks pass), and
  * restart detection of unfinished tasks.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from core.task_manager.manager import TaskManager
from database.store import SQLiteStore

# Terminal + in-flight statuses.
STATUS_QUEUED = "QUEUED"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_BLOCKED = "BLOCKED"
STATUS_ROLLED_BACK = "ROLLED_BACK"

IN_FLIGHT = {STATUS_QUEUED, STATUS_RUNNING}

# The critical gate items: all must pass for COMPLETED. Others are advisory.
CRITICAL_CHECKS = ("execution", "tests", "verification")
ADVISORY_CHECKS = ("regression", "security", "health", "git", "deploy", "memory")


def _load_result(task: dict[str, Any]) -> dict[str, Any]:
    raw = task.get("result")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def evaluate_gate(checklist: dict[str, bool]) -> tuple[str, list[str]]:
    """Return (status, failed_critical_items) per the final verification gate."""
    failed = [k for k in CRITICAL_CHECKS if not checklist.get(k)]
    if not checklist.get("execution"):
        return STATUS_FAILED, failed
    if failed:
        return STATUS_FAILED, failed
    return STATUS_COMPLETED, []


class TaskLedger:
    def __init__(self, store: Optional[SQLiteStore] = None):
        self.store = store or SQLiteStore()
        self.tm = TaskManager(self.store)

    # ── lifecycle ────────────────────────────────────────────────────────
    def open(self, request: str, intent: str = "", mode: str = "") -> str:
        task = self.tm.create(title=(request or "")[:200], description=intent, priority=6)
        result = {
            "mode": mode,
            "intent": intent,
            "events": [],
            "checklist": {},
            "verification": {},
        }
        self.tm.update(task["id"], status=STATUS_RUNNING, current_step="understand", result=result)
        return task["id"]

    def log(self, task_id: str, phase: str, message: str = "", level: str = "info", **data: Any) -> None:
        task = self.store.get_task(task_id)
        if not task:
            return
        result = _load_result(task)
        events = result.get("events") or []
        events.append(
            {
                "phase": phase,
                "message": message,
                "level": level,
                "data": data,
                "ts": time.time(),
            }
        )
        result["events"] = events[-200:]
        self.tm.update(task_id, current_step=phase, result=result)

    def set_retry(self, task_id: str, retry_count: int) -> None:
        self.tm.update(task_id, retries=retry_count)

    def block(self, task_id: str, reason: str, missing: Optional[list[str]] = None) -> None:
        task = self.store.get_task(task_id)
        result = _load_result(task) if task else {}
        result["blocked_reason"] = reason
        result["missing_capabilities"] = missing or []
        self.tm.update(task_id, status=STATUS_BLOCKED, result=result)

    def finalize(
        self,
        task_id: str,
        checklist: dict[str, bool],
        verification: dict[str, Any],
        message: str = "",
    ) -> dict[str, Any]:
        status, failed = evaluate_gate(checklist)
        task = self.store.get_task(task_id)
        result = _load_result(task) if task else {}
        result["checklist"] = checklist
        result["verification"] = verification
        result["failed_critical"] = failed
        result["final_message"] = message
        self.tm.set_status(task_id, status, progress=1.0 if status == STATUS_COMPLETED else 0.9)
        self.tm.update(task_id, result=result)
        return {"status": status, "failed_critical": failed}

    # ── queries ──────────────────────────────────────────────────────────
    def get(self, task_id: str) -> Optional[dict[str, Any]]:
        return self.store.get_task(task_id)

    def latest(self) -> Optional[dict[str, Any]]:
        tasks = self.store.list_tasks()
        return tasks[0] if tasks else None

    def unfinished(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for status in IN_FLIGHT:
            out.extend(self.store.list_tasks(status))
        return out

    def status_text(self, task_id: Optional[str] = None) -> str:
        task = self.get(task_id) if task_id else self.latest()
        if not task:
            return "Kayıtlı görev yok."
        result = _load_result(task)
        checklist = result.get("checklist") or {}
        marks = []
        for k in CRITICAL_CHECKS:
            marks.append(f"{'✅' if checklist.get(k) else '⬜'} {k}")
        lines = [
            f"🆔 {task.get('id')}",
            f"Görev: {task.get('title')}",
            f"Durum: {_status_emoji(task.get('status'))} {task.get('status')}",
            f"Aşama: {task.get('current_step') or '-'}",
            f"Retry: {task.get('retries') or 0}",
        ]
        if result.get("blocked_reason"):
            lines.append(f"Engel: {result['blocked_reason']}")
        if checklist:
            lines.append("Kapı: " + "  ".join(marks))
        return "\n".join(lines)


def _status_emoji(status: Optional[str]) -> str:
    return {
        STATUS_COMPLETED: "🟢",
        STATUS_RUNNING: "🟡",
        STATUS_QUEUED: "⏳",
        STATUS_FAILED: "🔴",
        STATUS_BLOCKED: "⛔",
        STATUS_ROLLED_BACK: "↩️",
    }.get(status or "", "•")
