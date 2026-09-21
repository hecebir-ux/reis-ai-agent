from __future__ import annotations

import re
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_SECRET_KEYS = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)",
    re.I,
)

_CRITICAL_HINTS = (
    "format",
    "diskpart",
    "reg delete",
    "shutdown",
    "rmdir /s",
    "del /f /s /q",
    "production",
    "deploy",
    "git push",
    "drop table",
)

_HIGH_HINTS = (
    "delete",
    "unlink",
    "remove",
    "credential",
    "token",
    "password",
    "system32",
    "appdata",
    "executable",
    ".exe",
    "taskkill",
)


def classify_risk(action: str, payload: str = "") -> RiskLevel:
    text = f"{action} {payload}".lower()
    if any(h in text for h in _CRITICAL_HINTS):
        return RiskLevel.CRITICAL
    if any(h in text for h in _HIGH_HINTS):
        return RiskLevel.HIGH
    if any(k in text for k in ("write", "edit", "install", "pip", "npm", "browser", "mouse", "keyboard")):
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def requires_approval(level: RiskLevel, safe_mode: bool = True) -> bool:
    if level == RiskLevel.CRITICAL:
        return True
    if safe_mode and level == RiskLevel.HIGH:
        return True
    return False


def redact(text: str) -> str:
    if not text:
        return text
    lines = []
    for line in str(text).splitlines():
        if _SECRET_KEYS.search(line):
            lines.append(_SECRET_KEYS.sub(r"\1=***", line))
        else:
            lines.append(line)
    return "\n".join(lines)


def looks_like_secret(text: str) -> bool:
    return bool(_SECRET_KEYS.search(text or ""))
