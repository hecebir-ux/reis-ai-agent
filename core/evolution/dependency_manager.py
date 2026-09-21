from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import config
from core.evolution.scan_util import iter_project_py


class DependencyManager:
    def analyze(self, root: Path | None = None) -> dict[str, Any]:
        base = Path(root or config.BASE_DIR)
        req = base / "requirements.txt"
        pyproject = base / "pyproject.toml"
        declared = _parse_req(req)
        if pyproject.exists():
            declared |= _parse_pyproject(pyproject)
        imported: set[str] = set()
        for p in iter_project_py(base):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imported.add(a.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
        mapping = {"bs4": "beautifulsoup4", "dotenv": "python-dotenv"}
        missing = []
        for name in sorted(imported):
            pip = mapping.get(name, name)
            if name in {"config", "core", "tools", "tests", "database", "plugins", "api", "ui", "agents"}:
                continue
            if pip.lower() not in {d.lower() for d in declared} and not _stdlib(name):
                if name not in {"psutil"}:
                    missing.append(name)
        return {
            "ok": True,
            "declared": sorted(declared),
            "missing_in_requirements": missing,
            "has_pyproject": pyproject.exists(),
            "has_requirements": req.exists(),
        }

    def propose_update(self, package: str) -> dict[str, Any]:
        return {
            "ok": True,
            "action": "CHECK",
            "package": package,
            "note": "Körlemesine güncelleme yok. Compatibility + test sonrası uygulanır.",
        }

    def apply_missing_declarations(self, packages: list[str] | None = None) -> dict[str, Any]:
        """Sadece requirements.txt'e eksik satır ekler; pip install yapmaz."""
        analysis = self.analyze()
        missing = packages or analysis.get("missing_in_requirements") or []
        allowed = {"psutil", "pillow", "beautifulsoup4", "python-dotenv"}
        req = config.BASE_DIR / "requirements.txt"
        original = req.read_text(encoding="utf-8") if req.exists() else ""
        added: list[str] = []
        lines = original.splitlines()
        existing = {ln.split("==")[0].split(">=")[0].strip().lower() for ln in lines if ln.strip() and not ln.startswith("#")}
        for pkg in missing:
            name = {"bs4": "beautifulsoup4", "dotenv": "python-dotenv", "PIL": "pillow"}.get(pkg, pkg)
            if name.lower() not in allowed:
                continue
            if name.lower() in existing:
                continue
            lines.append(f"{name}")
            added.append(name)
        if not added:
            return {"ok": True, "changed": False, "added": [], "analysis": analysis}
        new_text = "\n".join(lines).rstrip() + "\n"
        backup = original
        req.write_text(new_text, encoding="utf-8")
        from core.evolution.self_tester import SelfTester

        test = SelfTester().run_file_import(config.BASE_DIR / "config.py")
        if not test.get("ok"):
            req.write_text(backup, encoding="utf-8")
            return {"ok": False, "rolled_back": True, "added": added, "test": test}
        return {"ok": True, "changed": True, "added": added, "rolled_back": False}


def _parse_req(path: Path) -> set[str]:
    out: set[str] = set()
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(re.split(r"[=<>\[]", line, maxsplit=1)[0].strip())
    return out


def _parse_pyproject(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'"([A-Za-z0-9_-]+)==', text))


def _stdlib(name: str) -> bool:
    import sys

    return name in getattr(sys, "stdlib_module_names", set()) or name in {
        "typing", "pathlib", "json", "os", "sys", "re", "time", "sqlite3",
        "subprocess", "threading", "shutil", "ast", "enum", "http", "urllib",
        "dataclasses", "collections", "functools", "tempfile", "traceback",
        "platform", "io", "uuid", "copy", "hashlib", "datetime", "logging",
        "argparse", "inspect", "contextlib", "concurrent", "unittest",
    }
