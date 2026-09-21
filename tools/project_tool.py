from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config


class ProjectAnalyzer:
    def analyze(self, project_dir: str) -> dict[str, Any]:
        root = Path(project_dir)
        if not root.exists():
            return {"success": False, "error": "Proje bulunamadı"}
        files = [p for p in root.rglob("*") if p.is_file() and ".venv" not in p.parts and "__pycache__" not in p.parts]
        names = [p.name.lower() for p in files]
        deps: list[str] = []
        req = root / "requirements.txt"
        pkg = root / "package.json"
        if req.exists():
            deps = [ln.strip() for ln in req.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip() and not ln.startswith("#")]
        npm = {}
        if pkg.exists():
            try:
                npm = json.loads(pkg.read_text(encoding="utf-8"))
            except Exception:
                npm = {}
        framework = "unknown"
        if "manage.py" in names:
            framework = "django"
        elif any(n in names for n in ("app.py", "main.py")) and any("flask" in d.lower() for d in deps):
            framework = "flask"
        elif any("fastapi" in d.lower() for d in deps):
            framework = "fastapi"
        elif "package.json" in names:
            framework = "node"
        elif any(n.endswith(".py") for n in names):
            framework = "python"
        entry = None
        for cand in ("main.py", "app.py", "index.js", "manage.py"):
            if (root / cand).exists():
                entry = cand
                break
        tests = [str(p.relative_to(root)) for p in files if p.name.startswith("test_") or p.name.endswith("_test.py") or p.name == "test.py"]
        git = (root / ".git").exists() or (config.BASE_DIR / ".git").exists()
        tree = sorted(str(p.relative_to(root)) for p in files)[:80]
        return {
            "success": True,
            "path": str(root.resolve()),
            "file_count": len(files),
            "tree": tree,
            "dependencies": deps,
            "npm": npm.get("dependencies", {}),
            "entry_point": entry,
            "tests": tests,
            "git": git,
            "framework": framework,
            "build_system": "pip" if req.exists() else ("npm" if pkg.exists() else "none"),
        }
