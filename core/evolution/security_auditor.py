from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import config
from core.evolution.scan_util import iter_project_py, rel
from core.security import looks_like_secret


class SecurityAuditor:
    def audit(self, root: Path | None = None) -> dict[str, Any]:
        base = Path(root or config.BASE_DIR)
        findings: list[dict[str, Any]] = []
        for p in iter_project_py(base):
            text = p.read_text(encoding="utf-8", errors="replace")
            rel_p = rel(p, base)
            if looks_like_secret(text) and "redact" not in text:
                for i, line in enumerate(text.splitlines(), 1):
                    if looks_like_secret(line) and "os.getenv" not in line and not line.strip().startswith("#"):
                        if "getattr(config" in line or "config." in line:
                            continue
                        if re.search(r'=\s*["\'][^"\']{8,}["\']', line):
                            findings.append({"file": rel_p, "kind": "hardcoded_secret", "line": i})
            if "shell=True" in text:
                for i, line in enumerate(text.splitlines(), 1):
                    s = line.strip()
                    if "shell=True" in s and not s.startswith("#") and "DANGEROUS" not in s and "_HINT" not in s:
                        findings.append({"file": rel_p, "kind": "unsafe_subprocess", "line": i})
                        break
            if "rmtree" in text or "unlink(" in text:
                if "SAFE" not in text and "_is_safe_path" not in text:
                    findings.append({"file": rel_p, "kind": "uncontrolled_delete", "line": _line_of(text, "unlink(") or _line_of(text, "rmtree")})
            if ".." in text and "Path" in text and "resolve" not in text:
                findings.append({"file": rel_p, "kind": "path_traversal_risk"})
            if "eval(" in text or "exec(" in text:
                # self_healing uses exec for isolated heal tests — flag others
                if "self_healing.py" not in rel_p:
                    findings.append({"file": rel_p, "kind": "arbitrary_code", "line": _line_of(text, "eval(") or _line_of(text, "exec(")})
        return {"ok": True, "findings": findings[:100], "count": len(findings)}


def _line_of(text: str, needle: str) -> int | None:
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return None
