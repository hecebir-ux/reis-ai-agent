from __future__ import annotations

import shutil
import time
from pathlib import Path

import config
from tools.filesystem import FileSystemTool


class BackupEngine:
    def snapshot(self, project_dir: str) -> dict:
        src = Path(project_dir)
        if not src.exists():
            return {"success": False, "error": "Kaynak yok"}
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = Path(config.BACKUPS_DIR) / f"{src.name}-{stamp}"
        fs = FileSystemTool()
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".venv", "__pycache__"))
            return {"success": True, "path": str(dest)}
        except Exception as e:
            return {"success": False, "error": str(e)}
