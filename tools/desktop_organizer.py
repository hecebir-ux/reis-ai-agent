"""Windows Desktop organizer — dry_run default, no irreversible deletes."""
from __future__ import annotations

import shutil
from pathlib import Path

GROUPS = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".xlsx", ".xls", ".ppt", ".pptx"},
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".ts", ".json", ".html", ".css"},
}


def organize(desktop: str | Path | None = None, dry_run: bool = True) -> dict:
    root = Path(desktop) if desktop else Path.home() / "Desktop"
    if not root.exists():
        return {"ok": False, "error": f"Desktop yok: {root}"}
    plan = []
    for item in root.iterdir():
        if item.is_dir() or item.name.startswith("."):
            continue
        dest_name = "Other"
        ext = item.suffix.lower()
        for folder, exts in GROUPS.items():
            if ext in exts:
                dest_name = folder
                break
        dest = root / dest_name / item.name
        plan.append({"src": str(item), "dst": str(dest)})
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.move(str(item), str(dest))
    return {"ok": True, "dry_run": dry_run, "moves": plan, "count": len(plan)}
