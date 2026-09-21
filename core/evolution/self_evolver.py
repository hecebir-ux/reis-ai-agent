from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any, Callable

import config
from core.evolution.safe_auto_update import UpdateLevel, classify_update, may_auto_apply
from core.evolution.self_tester import SelfTester
from tools.filesystem import FileSystemTool


class SelfEvolver:
    """Backup → plan → temp → syntax → test → validate → commit | rollback."""

    def __init__(self, tester: SelfTester | None = None):
        self.tester = tester or SelfTester()
        self.fs = FileSystemTool()
        self.log_path = config.LOGS_DIR / "evolution.jsonl"

    def apply_change(
        self,
        target: str | Path,
        new_content: str,
        extra_tests: list[Callable[[], dict]] | None = None,
        user_approved: bool = False,
        reason: str = "",
    ) -> dict[str, Any]:
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = config.BASE_DIR / target_path
        plan = {
            "target": str(target_path),
            "reason": reason,
            "bytes": len(new_content.encode("utf-8")),
        }
        level = classify_update(target_path, new_content)
        plan["level"] = level.value
        if not may_auto_apply(level, user_approved):
            self._log("blocked", plan)
            return {"ok": False, "status": "blocked", "level": level.value, "reason": "DANGEROUS: kullanıcı onayı gerekir"}

        original = target_path.read_text(encoding="utf-8") if target_path.exists() else None
        backup_dir = Path(config.BACKUPS_DIR) / "evolver" / time.strftime("%Y%m%d-%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / (target_path.name + ".bak")
        if original is not None:
            backup_file.write_text(original, encoding="utf-8")

        tmp = backup_dir / (target_path.name + ".tmp")
        tmp.write_text(new_content, encoding="utf-8")
        syn = _syntax_ok(tmp)
        if not syn["ok"]:
            self._log("syntax_fail", {**plan, "error": syn["error"]})
            return {"ok": False, "status": "rollback", "stage": "syntax", "error": syn["error"], "backup": str(backup_file)}

        write = self.fs.write_file(str(target_path), new_content)
        if not write.get("success"):
            self._rollback(target_path, original)
            return {"ok": False, "status": "rollback", "stage": "write", "error": write.get("error")}

        test_r = self.tester.run_file_import(target_path)
        if not test_r.get("ok"):
            self._rollback(target_path, original)
            self._log("import_fail", {**plan, "error": test_r})
            return {"ok": False, "status": "rollback", "stage": "import", "error": test_r, "backup": str(backup_file)}
        if extra_tests:
            for fn in extra_tests:
                r = fn()
                if not r.get("ok", r.get("success", False)):
                    self._rollback(target_path, original)
                    self._log("test_fail", {**plan, "error": r})
                    return {"ok": False, "status": "rollback", "stage": "test", "error": r, "backup": str(backup_file)}

        self._log("commit", plan)
        git_r = self._maybe_git_commit(target_path, reason)
        return {
            "ok": True,
            "status": "commit",
            "level": level.value,
            "target": str(target_path),
            "backup": str(backup_file) if original is not None else None,
            "plan": plan,
            "git": git_r,
        }

    def rollback_file(self, target: str | Path, backup: str | Path) -> dict[str, Any]:
        t = Path(target)
        b = Path(backup)
        if not b.exists():
            return {"ok": False, "error": "backup yok"}
        t.write_text(b.read_text(encoding="utf-8"), encoding="utf-8")
        self._log("manual_rollback", {"target": str(t), "backup": str(b)})
        return {"ok": True, "target": str(t)}

    def _maybe_git_commit(self, target: Path, reason: str) -> dict[str, Any]:
        if not getattr(config, "EVOLUTION_GIT_COMMIT", False):
            return {"skipped": True}
        try:
            from tools.git_tool import GitTool

            git = GitTool()
            msg = f"evolution: {reason or target.name}"[:72]
            return git.commit(msg)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _rollback(self, target: Path, original: str | None) -> None:
        if original is None:
            if target.exists():
                target.unlink()
            return
        target.write_text(original, encoding="utf-8")

    def _log(self, kind: str, payload: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, **payload}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def _syntax_ok(path: Path) -> dict[str, Any]:
    try:
        ast.parse(path.read_text(encoding="utf-8"))
        return {"ok": True}
    except SyntaxError as e:
        return {"ok": False, "error": f"{e.msg} line {e.lineno}"}
