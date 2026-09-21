from __future__ import annotations

import os
import time
from typing import Any


class Metrics:
    def __init__(self):
        self.task_times: list[float] = []
        self.tool_times: list[float] = []
        self.ollama_times: list[float] = []
        self.errors = 0
        self.calls = 0
        self.retries = 0
        self._task_t0: float | None = None
        self.startup_s: float = 0.0

    def record_startup(self, seconds: float) -> None:
        self.startup_s = seconds

    def record_ollama(self, seconds: float) -> None:
        self.ollama_times.append(seconds)
        self.calls += 1

    def record_tool(self, _name: str, seconds: float) -> None:
        self.tool_times.append(seconds)

    def record_retry(self) -> None:
        self.retries += 1

    def record_error(self) -> None:
        self.errors += 1

    def record_task_start(self) -> None:
        self._task_t0 = time.perf_counter()

    def record_task_end(self) -> None:
        if self._task_t0 is not None:
            self.task_times.append(time.perf_counter() - self._task_t0)
            self._task_t0 = None

    def snapshot(self) -> dict[str, Any]:
        cpu = None
        ram = None
        try:
            import psutil  # type: ignore
            cpu = psutil.cpu_percent(interval=0.05)
            ram = psutil.virtual_memory().percent
        except Exception:
            pass
        err_rate = round(self.errors / self.calls, 3) if self.calls else 0.0
        return {
            "cpu": cpu,
            "ram": ram,
            "pid": os.getpid(),
            "errors": self.errors,
            "retries": self.retries,
            "error_rate": err_rate,
            "startup_s": round(self.startup_s, 3),
            "avg_task_s": round(sum(self.task_times) / len(self.task_times), 3) if self.task_times else 0,
            "avg_tool_s": round(sum(self.tool_times) / len(self.tool_times), 3) if self.tool_times else 0,
            "avg_ollama_s": round(sum(self.ollama_times) / len(self.ollama_times), 3) if self.ollama_times else 0,
        }


metrics = Metrics()
