from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config
from core.security import classify_risk


class PluginManager:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or config.PLUGINS_DIR)
        self.root.mkdir(parents=True, exist_ok=True)
        self.loaded: dict[str, dict[str, Any]] = {}

    def discover(self) -> list[dict[str, Any]]:
        found = []
        for item in self.root.iterdir():
            if not item.is_dir():
                continue
            meta_path = item / "plugin.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            meta["path"] = str(item)
            meta["risk"] = classify_risk("plugin", meta.get("name", "")).value
            found.append(meta)
        return found

    def load(self, name: str) -> dict:
        for meta in self.discover():
            if meta.get("name") == name:
                if not meta.get("enabled", False):
                    return {"success": False, "error": "Plugin kapalı", "meta": meta}
                self.loaded[name] = meta
                return {"success": True, "meta": meta}
        return {"success": False, "error": "Plugin bulunamadı"}

    def disable(self, name: str) -> dict:
        self.loaded.pop(name, None)
        return {"success": True}

    def list_all(self) -> list[dict[str, Any]]:
        return self.discover()
