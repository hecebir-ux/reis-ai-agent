from __future__ import annotations

from enum import Enum
from pathlib import Path

import config


class UpdateLevel(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    DANGEROUS = "DANGEROUS"


_DANGEROUS_HINTS = (
    "registry",
    "reg add",
    "reg delete",
    "system32",
    "windows\\system",
    "format ",
    "diskpart",
    "shutdown",
    "os.remove",
    "shutil.rmtree",
    "unlink(",
    "admin",
    "elevate",
    "ctypes.windll",
)

_CAUTION_HINTS = (
    "subprocess",
    "shell=True",
    "eval(",
    "exec(",
    "pip install",
    "desktop",
    "appdata",
)


def classify_update(path: str | Path, content: str = "", action: str = "write") -> UpdateLevel:
    p = str(path).replace("/", "\\").lower()
    blob = f"{action} {p} {content}".lower()
    if any(h in blob for h in _DANGEROUS_HINTS):
        return UpdateLevel.DANGEROUS
    if "c:\\windows" in p or "c:\\program files" in p:
        return UpdateLevel.DANGEROUS
    try:
        rel = Path(path).resolve().relative_to(config.BASE_DIR.resolve())
        rel_s = str(rel).replace("\\", "/").lower()
    except Exception:
        return UpdateLevel.DANGEROUS
    if any(h in blob for h in _CAUTION_HINTS):
        return UpdateLevel.CAUTION
    if rel_s.startswith("core/") and not rel_s.startswith("core/evolution/"):
        return UpdateLevel.CAUTION
    if rel_s.startswith("tools/") or rel_s.startswith("tests/"):
        return UpdateLevel.CAUTION
    if rel_s.startswith("memory/") or rel_s.startswith("logs/") or rel_s.startswith("core/evolution/"):
        return UpdateLevel.SAFE
    return UpdateLevel.CAUTION


def may_auto_apply(level: UpdateLevel, user_approved: bool = False) -> bool:
    if level == UpdateLevel.DANGEROUS:
        return bool(user_approved)
    if level == UpdateLevel.CAUTION:
        return True  # tests+validation still required by evolver
    return True
