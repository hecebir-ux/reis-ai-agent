from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import config
from core.evolution.self_evolver import SelfEvolver
from core.evolution.self_reviewer import SelfReviewer
from core.evolution.self_tester import SelfTester
from core.evolution.safe_auto_update import classify_update, UpdateLevel


DESKTOP_MODULE = textwrap.dedent(
    '''
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
    '''
).lstrip()

DESKTOP_TEST = textwrap.dedent(
    '''
    import sys
    from pathlib import Path
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.desktop_organizer import organize

    def main():
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "a.txt").write_text("x", encoding="utf-8")
            (p / "b.png").write_bytes(b"x")
            r = organize(p, dry_run=True)
            assert r["ok"] and r["count"] == 2, r
            r2 = organize(p, dry_run=False)
            assert r2["ok"]
            assert (p / "Documents" / "a.txt").exists()
            assert (p / "Images" / "b.png").exists()
        print("DESKTOP_ORGANIZER_OK")

    if __name__ == "__main__":
        main()
    '''
).lstrip()


class SelfFeatureBuilder:
    def __init__(self):
        self.evolver = SelfEvolver()
        self.reviewer = SelfReviewer()
        self.tester = SelfTester()

    def plan(self, capability: str) -> dict[str, Any]:
        if "desktop" in capability.lower() or "masaüstü" in capability.lower() or "organization" in capability.lower():
            return {
                "capability": capability,
                "module": "tools/desktop_organizer.py",
                "test": "tests/test_desktop_organizer.py",
                "recipe": "desktop_organizer",
            }
        return {"capability": capability, "module": None, "recipe": None}

    def build(self, capability: str, user_approved: bool = False) -> dict[str, Any]:
        plan = self.plan(capability)
        if plan.get("recipe") != "desktop_organizer":
            return {"ok": False, "reason": "no_safe_recipe", "plan": plan}
        review = self.reviewer.review_source(DESKTOP_MODULE, plan["module"])
        if not review.get("ok"):
            return {"ok": False, "stage": "review", "review": review, "plan": plan}
        level = classify_update(config.BASE_DIR / plan["module"], DESKTOP_MODULE)
        if level == UpdateLevel.DANGEROUS and not user_approved:
            return {"ok": False, "stage": "policy", "level": level.value, "plan": plan}

        test_path = config.BASE_DIR / plan["test"]
        target = config.BASE_DIR / plan["module"]
        applied = self.evolver.apply_change(
            target,
            DESKTOP_MODULE,
            extra_tests=[lambda: self._write_and_run_test(test_path, DESKTOP_TEST)],
            reason="feature: desktop organizer",
        )
        if not applied.get("ok"):
            return {"ok": False, "stage": "evolver", "apply": applied, "plan": plan, "review": review}
        if not test_path.exists():
            test_path.write_text(DESKTOP_TEST, encoding="utf-8")
        return {"ok": True, "plan": plan, "review": review, "apply": applied}

    def _write_and_run_test(self, path: Path, content: str) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return self.tester.run_pytest_or_script(path)
