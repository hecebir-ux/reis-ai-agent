from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from core.evolution.safe_auto_update import classify_update


class SelfReviewer:
    def review_source(self, source: str, path: str = "snippet.py") -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return {"ok": False, "score": 0, "issues": [{"kind": "syntax", "detail": str(e)}]}

        fn_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                fn_names.append(node.name)
                if len(node.body) > 80:
                    issues.append({"kind": "complexity", "detail": f"{node.name} too long"})
                has_try = any(isinstance(n, ast.Try) for n in ast.walk(node))
                if node.name.startswith(("run", "apply", "write", "delete")) and not has_try:
                    issues.append({"kind": "error_handling", "detail": f"{node.name} no try/except"})
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append({"kind": "bare_except", "detail": f"line {node.lineno}"})
        dup = {n for n in fn_names if fn_names.count(n) > 1}
        for n in dup:
            issues.append({"kind": "duplicated_code", "detail": n})
        level = classify_update(path, source)
        if "eval(" in source or "exec(" in source:
            # ignore scanners that only mention these as string patterns
            if not any(x in path.replace("\\", "/") for x in ("self_diagnostics.py", "security_auditor.py", "self_reviewer.py", "self_healing.py", "auto_patcher.py")):
                issues.append({"kind": "security", "detail": "eval/exec"})
        score = max(0, 100 - 12 * len(issues))
        # truncated snippets may fail parse — treat incomplete AST as soft
        if any(i["kind"] == "syntax" for i in issues) and source.count("\n") < 20:
            return {"ok": False, "score": 0, "issues": issues, "level": level.value, "maintainability": "incomplete"}
        return {
            "ok": score >= 50 and not any(i["kind"] == "syntax" for i in issues),
            "score": score,
            "issues": issues,
            "level": level.value,
            "maintainability": "ok" if score >= 70 else "needs_work",
        }

    def review_file(self, path: str | Path) -> dict[str, Any]:
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        return self.review_source(text, str(p))

    def review_with_llm(self, source: str, llm=None) -> dict[str, Any]:
        base = self.review_source(source)
        if llm is None:
            return {**base, "llm": False}
        try:
            from core.model_router.router import ModelRouter

            router = ModelRouter(llm)
            router.apply("REVIEW")
            prompt = (
                "Kısa kod incelemesi. Sadece sorun listesi ver. Kod:\n"
                + source[:2500]
            )
            note = llm.generate(prompt, max_tokens=200, temperature=0.1, use_code_model=True)
            base["llm_notes"] = (note or "")[:800]
            base["llm"] = True
        except Exception as e:
            base["llm"] = False
            base["llm_error"] = str(e)
        return base
