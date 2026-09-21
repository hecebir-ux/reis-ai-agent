from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import config
from core.evolution.scan_util import iter_project_py, rel


STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {
    "typing", "pathlib", "json", "os", "sys", "re", "time", "subprocess",
    "threading", "uuid", "shutil", "ast", "dataclasses", "enum", "http",
    "urllib", "sqlite3", "platform", "io", "collections", "functools",
    "itertools", "tempfile", "copy", "traceback", "inspect", "hashlib",
    "datetime", "logging", "argparse", "contextlib", "concurrent",
}


class SelfDiagnostics:
    def scan(self, root: Path | None = None) -> dict[str, Any]:
        base = Path(root or config.BASE_DIR)
        problems: list[dict[str, Any]] = []
        missing_capabilities: list[str] = []
        performance_issues: list[str] = []
        security_issues: list[dict[str, Any]] = []
        test_gaps: list[str] = []
        recommendations: list[str] = []

        py_files = iter_project_py(base)
        defined_funcs: dict[str, list[str]] = {}
        imports_used: set[str] = set()
        third_party: set[str] = set()

        for path in py_files:
            text = _read(path)
            rel_p = rel(path, base)
            if text is None:
                problems.append({"file": rel_p, "kind": "io", "detail": "okunamadı"})
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError as e:
                problems.append({"file": rel_p, "kind": "syntax", "detail": f"{e.msg} line {e.lineno}"})
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        imports_used.add(top)
                        if top not in STDLIB and not _is_local(top, base):
                            third_party.add(top)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    imports_used.add(top)
                    if top not in STDLIB and not _is_local(top, base):
                        third_party.add(top)
                elif isinstance(node, ast.FunctionDef):
                    defined_funcs.setdefault(rel_p, []).append(node.name)
                    if node.name.startswith("todo"):
                        problems.append({"file": rel_p, "kind": "todo_fn", "detail": node.name})
                elif isinstance(node, ast.ClassDef):
                    defined_funcs.setdefault(rel_p, []).append(node.name)
                elif isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        problems.append({"file": rel_p, "kind": "bare_except", "detail": f"line {node.lineno}"})
                    elif node.body and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        problems.append({"file": rel_p, "kind": "swallowed_exception", "detail": f"line {node.lineno}"})

            for i, line in enumerate(text.splitlines(), 1):
                s = line.strip()
                if s.startswith("#") and any(k in s.upper() for k in ("TODO", "FIXME", "XXX", "HACK")):
                    problems.append({"file": rel_p, "kind": "todo", "detail": f"L{i}: {s[:80]}"})
                if "eval(" in s or "exec(" in s:
                    security_issues.append({"file": rel_p, "kind": "arbitrary_code", "detail": f"L{i}"})
                if "shell=True" in s and "subprocess" in text and not s.startswith("#"):
                    if "DANGEROUS" not in s and "_HINT" not in s:
                        security_issues.append({"file": rel_p, "kind": "unsafe_shell", "detail": f"L{i}"})
                if any(k in s.lower() for k in ("api_key =", "password =", "secret =", "token =")) and "os.getenv" not in s:
                    if "getattr(config" in s or "config." in s:
                        pass
                    elif not s.strip().startswith("#") and "***" not in s and "redact" not in s:
                        security_issues.append({"file": rel_p, "kind": "hardcoded_secret", "detail": f"L{i}: {s[:60]}"})

            unused = _unused_imports(tree)
            for name in unused:
                problems.append({"file": rel_p, "kind": "unused_import", "detail": name})

        req_names = _requirements(base / "requirements.txt")
        for pkg in sorted(third_party):
            if pkg in {"config"}:
                continue
            pip_name = {"bs4": "beautifulsoup4", "dotenv": "python-dotenv", "PIL": "pillow"}.get(pkg, pkg)
            if pip_name.lower() not in req_names and pkg not in {"psutil"}:
                problems.append({"file": "requirements.txt", "kind": "dependency", "detail": f"import {pkg} requirements'ta yok"})

        tests_dir = base / "tests"
        tested = set()
        if tests_dir.exists():
            for t in tests_dir.glob("test_*.py"):
                tested.add(t.stem.replace("test_", ""))
        core_mods = [rel(p, base) for p in py_files if "core" in p.parts]
        for m in core_mods:
            stem = Path(m).stem
            if stem in {"__init__"}:
                continue
            if stem not in tested and f"test_{stem}" not in tested:
                if stem in {"self_diagnostics", "self_evolver", "self_healing", "loop"}:
                    test_gaps.append(m)

        evo = base / "core" / "evolution"
        if not (evo / "self_diagnostics.py").exists():
            missing_capabilities.append("Self diagnostics")
        if not (base / "tools" / "desktop_organizer.py").exists():
            missing_capabilities.append("Desktop organization tool missing.")
        if not (config.MEMORY_DIR / "project_map.json").exists():
            missing_capabilities.append("Project map is stale or missing.")

        if any(p["kind"] == "syntax" for p in problems):
            recommendations.append("Sözdizimi hatalarını self-healer ile düzelt.")
        if missing_capabilities:
            recommendations.append("Eksik yetenekler için feature builder + test + commit kullan.")
        if test_gaps:
            recommendations.append("Kritik core modülleri için birim test üret.")
        if security_issues:
            recommendations.append("Güvenlik auditor çıktısını CAUTION/DANGEROUS politikasıyla işle.")
        performance_issues.extend(_perf_hints(base))

        return {
            "problems": problems[:200],
            "missing_capabilities": missing_capabilities,
            "performance_issues": performance_issues,
            "security_issues": security_issues[:80],
            "test_gaps": test_gaps[:40],
            "recommendations": recommendations,
            "stats": {
                "python_files": len(py_files),
                "functions_sampled": sum(len(v) for v in defined_funcs.values()),
            },
        }


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _is_local(name: str, base: Path) -> bool:
    return (base / name).exists() or (base / f"{name}.py").exists()


def _unused_imports(tree: ast.AST) -> list[str]:
    imported: list[tuple[str, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append((alias.asname or alias.name.split(".")[0], node))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                imported.append((alias.asname or alias.name, node))
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            used.add(node.value.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # symbols listed in __all__ count as used
            used.add(node.value)
    unused = []
    for name, node in imported:
        if name not in used and name not in {"__future__", "annotations"}:
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            unused.append(name)
    return unused[:8]


def _requirements(path: Path) -> set[str]:
    names: set[str] = set()
    if not path.exists():
        return names
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip().lower()
        names.add(name)
    return names


def _perf_hints(base: Path) -> list[str]:
    hints = []
    llm = base / "core" / "llm_client.py"
    if llm.exists():
        text = llm.read_text(encoding="utf-8", errors="replace")
        if "timeout" not in text and "OLLAMA_TIMEOUT" not in text:
            hints.append("LLM istemcisinde timeout yok")
    return hints
