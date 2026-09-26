"""Error Memory — remember failures and which fixes worked (or didn't).

Before retrying, the agent checks whether it has seen an error signature
before, so it can reuse a known-good fix and avoid repeating a fix that has
already failed. Backed by the existing SQLite knowledge store.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

_EXC_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning))")
_SIG_PREFIX = "ERRSIG"


class ErrorMemory:
    def __init__(self, store: Any):
        self.store = store

    @staticmethod
    def signature(error_text: str) -> str:
        """Stable short signature from the exception type + last meaningful line."""
        text = (error_text or "").strip()
        exc_types = _EXC_RE.findall(text)
        core = exc_types[-1] if exc_types else ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        tail = lines[-1] if lines else text[:100]
        # Drop volatile bits (paths, line numbers, hex addresses).
        tail = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", tail)
        tail = re.sub(r"line \d+", "line N", tail)
        tail = re.sub(r"[\"'][^\"']*[\\/][^\"']*[\"']", "PATH", tail)
        base = f"{core}|{tail}"[:200]
        digest = hashlib.sha1(base.encode("utf-8", "replace")).hexdigest()[:16]
        return f"{_SIG_PREFIX}:{digest}"

    def record(
        self,
        error_text: str,
        fix: str,
        success: bool,
        root_cause: str = "",
        project: Optional[str] = None,
    ) -> str:
        sig = self.signature(error_text)
        problem = f"{sig} {(root_cause or error_text)[:120]}"
        try:
            self.store.add_knowledge(
                problem=problem,
                solution=(fix or "")[:400],
                source="error",
                project=project,
                success=success,
            )
        except Exception:
            pass
        return sig

    def known_fixes(self, error_text: str) -> list[dict[str, Any]]:
        sig = self.signature(error_text)
        try:
            return self.store.search_knowledge(sig)
        except Exception:
            return []

    def successful_fix(self, error_text: str) -> Optional[str]:
        for row in self.known_fixes(error_text):
            if row.get("success") in (1, True):
                return row.get("solution")
        return None

    def has_failed_fix(self, error_text: str, fix: str) -> bool:
        needle = (fix or "")[:120]
        for row in self.known_fixes(error_text):
            if row.get("success") in (0, False) and needle and needle in (row.get("solution") or ""):
                return True
        return False
