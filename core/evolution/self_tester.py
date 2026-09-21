from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import config


def _pythonpath_env() -> dict[str, str]:
    env = dict(os.environ)
    extra = str(config.BASE_DIR)
    env["PYTHONPATH"] = extra + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


class SelfTester:
    def run_file_import(self, path: Path) -> dict[str, Any]:
        p = Path(path)
        try:
            ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            return {"ok": False, "error": f"syntax: {e}"}
        rel = None
        try:
            rel = p.resolve().relative_to(config.BASE_DIR.resolve())
        except ValueError:
            rel = p
        mod = str(rel).replace("\\", "/").replace("/", ".").removesuffix(".py")
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        r = subprocess.run(
            [sys.executable, "-c", f"import {mod}"],
            cwd=str(config.BASE_DIR),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
            env=_pythonpath_env(),
        )
        return {
            "ok": r.returncode == 0,
            "stdout": r.stdout[-400:],
            "stderr": r.stderr[-400:],
            "exit_code": r.returncode,
            "module": mod,
        }

    def run_pytest_or_script(self, test_path: str | Path, cwd: str | Path | None = None) -> dict[str, Any]:
        p = Path(test_path)
        work = str(cwd or config.BASE_DIR)
        started = time.perf_counter()
        cmd = [sys.executable, str(p)]
        env = _pythonpath_env()
        r = subprocess.run(
            cmd,
            cwd=work,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return {
            "ok": r.returncode == 0,
            "success": r.returncode == 0,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "exit_code": r.returncode,
            "duration": round(time.perf_counter() - started, 3),
        }

    def generate_smoke_test(self, module_rel: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        mod = module_rel.replace("\\", "/").replace("/", ".").removesuffix(".py")
        dest.write_text(
            f"# auto-generated smoke\nimport importlib\nm = importlib.import_module({mod!r})\nprint('SMOKE_OK', m.__name__)\n",
            encoding="utf-8",
        )
        return dest

    def create_and_run(self, module_rel: str, max_fix: int = 2) -> dict[str, Any]:
        dest = Path(config.LOGS_DIR) / "_generated_smoke.py"
        self.generate_smoke_test(module_rel, dest)
        last: dict[str, Any] = {}
        for i in range(max_fix):
            last = self.run_pytest_or_script(dest)
            if last.get("ok"):
                return {**last, "fixed": True, "attempts": i + 1}
            dest.write_text(
                f"# retry smoke\nimport importlib\nm = importlib.import_module({module_rel.replace(chr(92), '/').replace('/', '.').removesuffix('.py')!r})\nprint('SMOKE_OK', getattr(m, '__name__', ''))\n",
                encoding="utf-8",
            )
        return {**last, "fixed": False, "attempts": max_fix}
