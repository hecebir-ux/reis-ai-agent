from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import config
from core.evolution.scan_util import SKIP_DIRS, iter_project_py, rel


ROLE_HINTS = {
    "core": "çekirdek ajan mantığı",
    "core/agent": "MAX ajan döngüsü",
    "core/evolution": "self-evolution sistemleri",
    "core/model_router": "Ollama model seçimi",
    "core/intent": "doğal dil niyet sınıflama",
    "core/task_manager": "görev kuyruğu",
    "core/context": "sohbet bağlamı",
    "tools": "yerel araçlar (dosya, terminal, web)",
    "tests": "otomatik testler",
    "database": "SQLite bellek",
    "plugins": "eklentiler",
    "api": "yerel HTTP API",
    "ui": "IDE/spec katmanı",
    "agents": "ajan girişleri",
}


class ProjectMapper:
    def __init__(self, root: Path | None = None):
        self.root = Path(root or config.BASE_DIR)
        self.map_path = config.MEMORY_DIR / "project_map.json"

    def build(self) -> dict[str, Any]:
        packages: dict[str, dict[str, Any]] = {}
        files_meta: list[dict[str, Any]] = []
        for py in iter_project_py(self.root):
            r = rel(py, self.root)
            parts = r.split("/")
            pkg = parts[0] if len(parts) > 1 else "root"
            if len(parts) >= 2 and pkg == "core":
                pkg = "/".join(parts[:2]) if parts[1] != Path(r).name else "core"
            bucket = packages.setdefault(
                pkg,
                {"role": ROLE_HINTS.get(pkg, ROLE_HINTS.get(parts[0], "proje dosyası")), "files": []},
            )
            bucket["files"].append(r)
            files_meta.append({"path": r, "size": py.stat().st_size, "role": bucket["role"]})

        tree = sorted({p.parts[0] for p in self.root.iterdir() if p.name not in SKIP_DIRS and not p.name.startswith(".")})
        data = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "root": str(self.root),
            "top_level": tree,
            "packages": packages,
            "file_count": len(files_meta),
            "files": files_meta[:400],
        }
        self.map_path.parent.mkdir(parents=True, exist_ok=True)
        self.map_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def load(self) -> dict[str, Any]:
        if self.map_path.exists():
            try:
                return json.loads(self.map_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return self.build()

    def describe(self, path: str) -> str:
        data = self.load()
        for f in data.get("files") or []:
            if f.get("path") == path.replace("\\", "/"):
                return f"{path}: {f.get('role')}"
        return f"{path}: haritada yok"
