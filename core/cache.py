from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float = 120.0, max_items: int = 256):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def make_key(*parts: Any) -> str:
        raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires, value = item
            if expires < time.time():
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self.max_items:
                oldest = min(self._data.items(), key=lambda kv: kv[1][0])[0]
                self._data.pop(oldest, None)
            self._data[key] = (time.time() + self.ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


tool_cache = TTLCache(ttl_seconds=90, max_items=128)
response_cache = TTLCache(ttl_seconds=45, max_items=64)
