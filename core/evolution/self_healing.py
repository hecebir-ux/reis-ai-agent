from __future__ import annotations

import ast
import traceback
from pathlib import Path
from typing import Any, Callable

import config
from core.evolution.knowledge import KnowledgeMemory
from core.evolution.self_evolver import SelfEvolver
from core.evolution.self_tester import SelfTester


def _max_heal() -> int:
    return int(getattr(config, "EVOLUTION_MAX_HEAL", 3) or 3)


class SelfHealing:
    """EXECUTE → ERROR → TRACEBACK → ROOT CAUSE → PATCH → TEST → RETRY (max 3) → ROLLBACK."""

    def __init__(self, evolver: SelfEvolver | None = None):
        self.evolver = evolver or SelfEvolver()
        self.tester = SelfTester()
        self.knowledge = KnowledgeMemory()

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        last_exc: BaseException | None = None
        limit = _max_heal()
        for i in range(1, limit + 1):
            try:
                value = fn(*args, **kwargs)
                return {"ok": True, "value": value, "attempts": i, "history": attempts}
            except Exception as e:
                last_exc = e
                tb = traceback.format_exc()
                cause = analyze_traceback(tb)
                attempts.append({"attempt": i, "error": f"{type(e).__name__}: {e}", "cause": cause})
                patched = self._try_patch(cause, tb)
                attempts[-1]["patch"] = patched
                if not patched.get("ok"):
                    continue
        if last_exc is not None:
            for h in reversed(attempts):
                b = (h.get("patch") or {}).get("backup")
                t = (h.get("patch") or {}).get("target")
                if b and t:
                    self.evolver.rollback_file(t, b)
                    break
        return {"ok": False, "attempts": limit, "history": attempts, "error": str(last_exc), "rolled_back": True}

    def _try_patch(self, cause: dict[str, Any], tb: str) -> dict[str, Any]:
        err = cause.get("error") or ""
        hits = self.knowledge.lookup(err[:120] or cause.get("root_cause") or "")
        path_s = cause.get("file")
        if not path_s:
            return {"ok": False, "reason": "no_file", "memory_hits": len(hits)}
        path = Path(path_s)
        try:
            path.resolve().relative_to(config.BASE_DIR.resolve())
        except ValueError:
            return {"ok": False, "reason": "outside_project"}
        if not path.exists() or path.suffix != ".py":
            return {"ok": False, "reason": "not_python"}
        original = path.read_text(encoding="utf-8")
        nxt = heuristic_fix(original, cause, err)
        if nxt is None or nxt == original:
            return {"ok": False, "reason": "no_heuristic", "memory_hits": len(hits)}
        applied = self.evolver.apply_change(path, nxt, reason=f"self-heal:{cause.get('root_cause')}")
        if applied.get("ok"):
            self.knowledge.remember(err[:200], "heuristic patch applied", source="self-heal", success=True)
        return applied

    def heal_source_file(self, path: Path | str, extra_fix: Callable[[str], str] | None = None) -> dict[str, Any]:
        p = Path(path)
        original = p.read_text(encoding="utf-8")
        code = original
        history = []
        for i in range(1, _max_heal() + 1):
            try:
                ast.parse(code)
                compile(code, str(p), "exec")
                ns: dict[str, Any] = {}
                exec(compile(code, str(p), "exec"), ns, ns)
                if "main" in ns and callable(ns["main"]):
                    ns["main"]()
                applied = self.evolver.apply_change(p, code, reason=f"self-heal attempt {i}")
                return {"ok": True, "attempts": i, "history": history, "apply": applied}
            except Exception as e:
                tb = traceback.format_exc()
                cause = analyze_traceback(tb)
                history.append({"attempt": i, "error": f"{type(e).__name__}: {e}", "cause": cause})
                nxt = extra_fix(code) if extra_fix else heuristic_fix(code, cause, str(e))
                if nxt is None or nxt == code:
                    p.write_text(original, encoding="utf-8")
                    return {"ok": False, "attempts": i, "history": history, "rolled_back": True, "reason": "no patch"}
                code = nxt
                p.write_text(code, encoding="utf-8")
        p.write_text(original, encoding="utf-8")
        return {"ok": False, "attempts": _max_heal(), "history": history, "rolled_back": True}


def analyze_traceback(tb: str) -> dict[str, Any]:
    file = None
    line = None
    err = tb.strip().splitlines()[-1] if tb.strip() else ""
    for row in tb.splitlines():
        if 'File "' in row and ", line " in row:
            try:
                file = row.split('File "')[1].split('"')[0]
                line = int(row.split(", line ")[1].split(",")[0])
            except Exception:
                pass
    root = "unknown"
    if "ZeroDivisionError" in tb:
        root = "division_by_zero"
    elif "SyntaxError" in tb:
        root = "syntax"
    elif "ModuleNotFoundError" in tb or "ImportError" in tb:
        root = "import"
    elif "NameError" in tb:
        root = "name"
    elif "FileNotFoundError" in tb:
        root = "missing_file"
    return {"file": file, "line": line, "error": err, "root_cause": root}


def heuristic_fix(code: str, cause: dict[str, Any], err: str) -> str | None:
    if cause.get("root_cause") == "division_by_zero" and " / " in code:
        if "if b ==" in code:
            return None
        if "return a / b" in code:
            return code.replace(
                "return a / b",
                'if b == 0:\n        return "HATA: Sifira bolunemez"\n    return a / b',
            )
    if "NameError" in err and "name '" in err:
        name = err.split("name '", 1)[1].split("'", 1)[0]
        if f"{name} =" not in code:
            return f"{name} = None\n{code}"
    return None
