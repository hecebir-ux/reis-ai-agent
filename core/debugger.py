from pathlib import Path
import config
from core.coder import Coder
from core.tester import Tester
from tools.filesystem import FileSystemTool
from tools.python_tool import PythonTool
from core.memory import Memory


class Debugger:
    def __init__(self, llm_client):
        self.coder = Coder(llm_client, FileSystemTool(), PythonTool())
        self.tester = Tester()
        self.fs = FileSystemTool()
        self.python = PythonTool()
        self.max_attempts = config.MAX_DEBUG_ATTEMPTS

    def auto_fix(self, session_id: str, memory: Memory, project_dir: str, test_result: dict, step_context: str = "", max_attempts: int = None) -> dict:
        errors = self.tester.extract_errors(test_result)
        if not errors:
            stderr = test_result.get("stderr", "")
            stdout = test_result.get("stdout", "")
            if stderr.strip():
                errors.append(stderr.strip())
            elif stdout.strip():
                errors.append(stdout.strip()[:2000])
            else:
                return {"fixed": False, "reason": "Belirgin hata ciktilari yakalanamadi"}

        attempt = 0
        limit = max_attempts if max_attempts is not None else self.max_attempts
        last_result = dict(test_result)

        while attempt < limit and errors:
            attempt += 1
            err_block = errors[0]
            err_info = self.python.analyze_python_error(err_block)

            target_file = err_info.get("file")
            if not target_file or not Path(target_file).is_absolute():
                candidates = list(Path(project_dir).rglob("*.py"))
                if candidates:
                    target_file = str(candidates[0])
                else:
                    return {"fixed": False, "reason": "Duzeltilecek hedef dosya bulunamadi", "attempts": attempt}

            try:
                read_r = self.fs.read_file(target_file)
            except Exception:
                read_r = {"success": False, "error": "dosya okunamadi"}
            if not read_r.get("success"):
                return {"fixed": False, "reason": f"Dosya okunamadi: {read_r.get('error')}", "attempts": attempt}

            original_code = read_r["content"]
            heuristic = self._heuristic_fix(original_code, err_info, err_block)
            if heuristic:
                fixed, new_code = True, heuristic
            else:
                fixed, new_code = self.coder.fix_code(target_file, original_code, err_info, step_context)
            if not fixed:
                attempt_info = f"Deneme {attempt}: LLM duzeltilmis kod donmedi"
                memory.add_error(session_id, f"debug_attempt_{attempt}", attempt_info)
                continue

            write_r = self.fs.write_file(target_file, new_code)
            if not write_r.get("success"):
                memory.add_error(session_id, f"debug_write_{attempt}", write_r.get("error", ""))
                continue

            memory.add_fix(
                session_id,
                error_summary=f"{err_info.get('error_type') or 'Hata'}: {(err_info.get('error_message') or '')[:80]}",
                fix_action=f"Dosya duzenlendi: {Path(target_file).name}",
                success=True,
            )

            new_test = self.tester.detect_and_run(project_dir)
            last_result = new_test

            if new_test.get("success"):
                memory.add_step(session_id, "debug", f"Deneme {attempt}: HATA DÜZELTILDI - {err_info.get('error_type', 'Hata')}", new_test)
                return {"fixed": True, "attempts": attempt, "last_result": new_test}

            errors = self.tester.extract_errors(new_test)
            if not errors:
                stderr = new_test.get("stderr", "")
                if stderr.strip():
                    errors.append(stderr)
            memory.add_step(session_id, "debug", f"Deneme {attempt}: Tekrar denenecek - hala hata var", new_test)

        return {"fixed": last_result.get("success", False), "attempts": attempt, "last_result": last_result}

    @staticmethod
    def _heuristic_fix(original_code: str, err_info: dict, err_block: str) -> str | None:
        blob = f"{err_info.get('error_type','')} {err_info.get('error_message','')} {err_block}"
        if "ZeroDivisionError" in blob and " / " in original_code:
            if "if b ==" in original_code or "if b==" in original_code:
                return None
            return original_code.replace(
                "return a / b",
                'if b == 0:\n        return "HATA: Sifira bolunemez"\n    return a / b',
            )
        if "NameError" in blob:
            msg = err_info.get("error_message") or ""
            name = None
            if "name '" in msg:
                name = msg.split("name '", 1)[1].split("'", 1)[0]
            if name and f"{name} =" not in original_code:
                return f"{name} = None\n{original_code}"
        return None
