from __future__ import annotations

import json
import subprocess
from pathlib import Path

import config
from core.security import classify_risk, requires_approval


class GitTool:
    def __init__(self, allow_push: bool = False):
        self.allow_push = allow_push

    def _run(self, args: list[str], cwd: str | None = None) -> dict:
        try:
            r = subprocess.run(
                ["git", *args],
                cwd=cwd or str(config.BASE_DIR),
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            return {
                "success": r.returncode == 0,
                "stdout": r.stdout,
                "stderr": r.stderr,
                "exit_code": r.returncode,
                "command": "git " + " ".join(args),
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "exit_code": -1, "command": "git"}

    def status(self, cwd: str | None = None) -> dict:
        return self._run(["status", "--short", "--branch"], cwd)

    def diff(self, cwd: str | None = None) -> dict:
        return self._run(["diff"], cwd)

    def log(self, n: int = 8, cwd: str | None = None) -> dict:
        return self._run(["log", f"-{n}", "--oneline"], cwd)

    def branch(self, cwd: str | None = None) -> dict:
        return self._run(["branch", "-a"], cwd)

    def commit(self, message: str, cwd: str | None = None) -> dict:
        self._run(["add", "-A"], cwd)
        return self._run(["commit", "-m", message], cwd)

    def checkout(self, ref: str, cwd: str | None = None) -> dict:
        return self._run(["checkout", ref], cwd)

    def merge(self, ref: str, cwd: str | None = None) -> dict:
        return self._run(["merge", ref], cwd)

    def push(self, cwd: str | None = None, approved: bool = False) -> dict:
        risk = classify_risk("git push", cwd or "")
        if config.GIT_PUSH_REQUIRES_APPROVAL and not (approved or self.allow_push):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Remote push kullanıcı izni olmadan yapılmaz.",
                "exit_code": -1,
                "risk": risk.value,
                "needs_approval": True,
            }
        if requires_approval(risk, config.SAFE_MODE) and not approved:
            return {"success": False, "stderr": "Onay gerekli", "needs_approval": True, "exit_code": -1, "stdout": ""}
        return self._run(["push"], cwd)
