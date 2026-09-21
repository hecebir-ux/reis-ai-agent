from __future__ import annotations

from pathlib import Path

import config

SKIP_DIRS = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "workspace",
    "backups",
    "cache",
    "logs",
    ".cursor",
}


def iter_project_py(root: Path | None = None) -> list[Path]:
    base = Path(root or config.BASE_DIR)
    out: list[Path] = []
    for p in base.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def rel(path: Path, root: Path | None = None) -> str:
    base = Path(root or config.BASE_DIR)
    try:
        return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
