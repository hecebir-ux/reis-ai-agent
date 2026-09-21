from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable

import config
from database.store import SQLiteStore

STATUSES = (
    "QUEUED",
    "RUNNING",
    "WAITING",
    "TESTING",
    "DEBUGGING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "PAUSED",
)


class TaskManager:
    def __init__(self, store: SQLiteStore | None = None):
        self.store = store or SQLiteStore()
        self._control: dict[str, str] = {}
        self._lock = threading.Lock()

    def create(
        self,
        title: str,
        description: str = "",
        priority: int = 5,
        plan: Any = None,
    ) -> dict[str, Any]:
        task = {
            "id": f"task_{uuid.uuid4().hex[:10]}",
            "title": title,
            "description": description,
            "status": "QUEUED",
            "priority": priority,
            "plan": plan or {},
            "current_step": "",
            "progress": 0.0,
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": None,
            "errors": [],
            "retries": 0,
            "result": {},
        }
        self.store.save_task(task)
        return task

    def update(self, task_id: str, **fields: Any) -> dict[str, Any] | None:
        current = self.store.get_task(task_id)
        if not current:
            return None
        current.update(fields)
        self.store.save_task(current)
        return current

    def set_status(self, task_id: str, status: str, step: str | None = None, progress: float | None = None) -> None:
        fields: dict[str, Any] = {"status": status}
        if step is not None:
            fields["current_step"] = step
        if progress is not None:
            fields["progress"] = progress
        if status in {"COMPLETED", "FAILED", "CANCELLED"}:
            fields["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.update(task_id, **fields)

    def control(self, task_id: str, action: str) -> str:
        action = action.upper()
        with self._lock:
            self._control[task_id] = action
        mapping = {
            "PAUSE": "PAUSED",
            "CANCEL": "CANCELLED",
            "STOP": "CANCELLED",
            "RESUME": "RUNNING",
        }
        if action in mapping:
            self.set_status(task_id, mapping[action])
        return action

    def should_stop(self, task_id: str) -> bool:
        with self._lock:
            return self._control.get(task_id) in {"STOP", "CANCEL"}

    def should_pause(self, task_id: str) -> bool:
        with self._lock:
            return self._control.get(task_id) == "PAUSE"

    def recover_unfinished(self) -> list[dict[str, Any]]:
        out = []
        for status in ("RUNNING", "WAITING", "TESTING", "DEBUGGING", "QUEUED", "PAUSED"):
            out.extend(self.store.list_tasks(status))
        return out


class TaskQueue:
    def __init__(self, manager: TaskManager, max_workers: int | None = None):
        self.manager = manager
        self.pool = ThreadPoolExecutor(max_workers=max_workers or config.MAX_PARALLEL_TASKS)
        self.futures: dict[str, Future] = {}

    def submit(self, task_id: str, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        self.manager.set_status(task_id, "RUNNING", step="execute", progress=0.05)

        def wrapped():
            try:
                if self.manager.should_stop(task_id):
                    self.manager.set_status(task_id, "CANCELLED")
                    return {"ok": False, "cancelled": True}
                result = fn(*args, **kwargs)
                ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
                self.manager.update(task_id, result=result, status="COMPLETED" if ok else "FAILED")
                return result
            except Exception as e:
                self.manager.update(task_id, status="FAILED", errors=[str(e)])
                raise

        fut = self.pool.submit(wrapped)
        self.futures[task_id] = fut
        return fut
