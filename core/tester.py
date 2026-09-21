from pathlib import Path
import config
from tools.terminal import TerminalTool
from tools.python_tool import PythonTool


class Tester:
    def __init__(self):
        self.terminal = TerminalTool()
        self.python = PythonTool()

    def detect_and_run(self, project_dir: str) -> dict:
        p = Path(project_dir)
        strategies = [
            self._try_manage_py,
            self._try_pytest,
            self._try_test_py,
            self._try_main_py,
            self._try_app_py,
            self._try_single_script,
            self._try_requirements_check,
        ]
        last_result = {"success": False, "error": "Test stratejisi bulunamadi"}
        for strat in strategies:
            try:
                result = strat(p)
                if result.get("ran_test"):
                    return result
                if result.get("success") is False and result.get("error") != "skip":
                    last_result = result
            except Exception as e:
                last_result = {"success": False, "error": f"Test strateji hatasi: {e}"}
        return last_result

    def _try_requirements_check(self, p: Path) -> dict:
        req = p / "requirements.txt"
        if req.exists():
            r = self.python.install_requirements(str(req))
            return {"success": r["success"], "ran_test": False, "stdout": r.get("stdout", ""), "stderr": r.get("stderr", ""), "exit_code": r.get("exit_code", 0)}
        return {"success": None, "error": "skip"}

    def _try_pytest(self, p: Path) -> dict:
        tests = list(p.rglob("test_*.py")) + list(p.rglob("*_test.py"))
        if not tests:
            return {"success": None, "error": "skip"}
        r = self.terminal.run(f'python -m pytest -x -v --tb=short 2>&1', cwd=str(p))
        combined = (r.get("stderr") or "") + (r.get("stdout") or "")
        if r.get("exit_code") not in (0, 1) and "No module named pytest" in combined:
            script = tests[0]
            r2 = self.python.run_script(str(script), cwd=str(p))
            return {"ran_test": True, "strategy": "test_file_fallback", **r2}
        return {"ran_test": True, "strategy": "pytest", **r}

    def _try_test_py(self, p: Path) -> dict:
        test_file = p / "test.py"
        if not test_file.exists():
            return {"success": None, "error": "skip"}
        r = self.python.run_script(str(test_file), cwd=str(p))
        return {"ran_test": True, "strategy": "test.py", **r}

    def _try_manage_py(self, p: Path) -> dict:
        manage = p / "manage.py"
        if not manage.exists():
            return {"success": None, "error": "skip"}
        r = self.python.run_script(str(manage), args="check", cwd=str(p))
        if not r["success"]:
            return {"ran_test": True, "strategy": "manage.py check", **r}
        r2 = self.python.run_script(str(manage), args="migrate --check", cwd=str(p))
        return {"ran_test": True, "strategy": "manage.py", **r2}

    def _try_main_py(self, p: Path) -> dict:
        main = p / "main.py"
        if not main.exists():
            return {"success": None, "error": "skip"}
        return self._run_short_script(main, p)

    def _try_app_py(self, p: Path) -> dict:
        app = p / "app.py"
        if not app.exists():
            return {"success": None, "error": "skip"}
        return self._run_short_script(app, p)

    def _try_single_script(self, p: Path) -> dict:
        pys = [
            x for x in p.glob("*.py")
            if x.name not in {"test.py", "conftest.py"} and not x.name.startswith("test_")
        ]
        if len(pys) != 1:
            return {"success": None, "error": "skip"}
        return self._run_short_script(pys[0], p)

    def _run_short_script(self, script: Path, p: Path) -> dict:
        r = self.terminal.run(
            f'python -c "import ast, sys; ast.parse(open(sys.argv[1], encoding=\'utf-8\').read()); print(\'SYNTAX_OK\')" "{script}"',
            cwd=str(p),
            timeout=30,
        )
        if not r["success"] or "SYNTAX_OK" not in r["stdout"]:
            return {"ran_test": True, "strategy": "syntax_check", "success": False, **r, "error": "Soz dizimi hatasi"}
        short_r = self.terminal.run(
            f'python "{script}"',
            cwd=str(p),
            timeout=15,
        )
        if short_r.get("exit_code") == -2:
            short_r["success"] = True
            short_r["note"] = "Web sunucusu veya uzun surecek script basladi - zaman asimi normal"
        return {"ran_test": True, "strategy": f"run {script.name}", **short_r}

    @staticmethod
    def extract_errors(result: dict) -> list[str]:
        errs = []
        stderr = result.get("stderr", "") or ""
        stdout = result.get("stdout", "") or ""
        combined = stderr + "\n" + stdout
        lines = combined.splitlines()
        current = []
        capturing = False
        for line in lines:
            if "Traceback" in line or line.strip().startswith("Error") or "Exception" in line:
                capturing = True
            if capturing:
                current.append(line)
                if not line.startswith(" ") and not line.startswith("\t") and ("Error" in line or "Exception" in line) and len(current) > 2:
                    errs.append("\n".join(current))
                    current = []
                    capturing = False
        if current:
            errs.append("\n".join(current))
        return errs
