import subprocess
import time
import config


class TerminalTool:
    def __init__(self):
        self.blocked_patterns = config.DANGEROUS_COMMANDS

    def _is_safe(self, command: str) -> tuple[bool, str]:
        cmd_lower = command.lower()
        for pattern in self.blocked_patterns:
            if pattern in cmd_lower:
                return False, f"Tehlikeli komut engellendi: {pattern}"
        return True, "OK"

    def run(self, command: str, cwd: str = None, timeout: int = None) -> dict:
        safe, reason = self._is_safe(command)
        if not safe:
            return {
                "success": False,
                "stdout": "",
                "stderr": reason,
                "exit_code": -1,
                "command": command,
                "duration": 0.0,
            }

        if timeout is None:
            timeout = config.COMMAND_TIMEOUT

        working_dir = cwd if cwd else str(config.WORKSPACE_DIR)

        started = time.perf_counter()
        result = {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "command": command,
            "duration": 0.0,
        }

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["exit_code"] = proc.returncode
            result["success"] = proc.returncode == 0

        except subprocess.TimeoutExpired as e:
            result["stderr"] = f"Komut zaman asimina ugradi ({timeout}s): {str(e)}"
            result["exit_code"] = -2
        except Exception as e:
            result["stderr"] = f"Komut hatasi: {type(e).__name__}: {str(e)}"
            result["exit_code"] = -3
        finally:
            result["duration"] = round(time.perf_counter() - started, 4)

        return result

    def run_python(self, script_path: str, args: str = "", cwd: str = None) -> dict:
        python_exe = self._find_python()
        cmd = f'"{python_exe}" "{script_path}" {args}'
        return self.run(cmd, cwd=cwd)

    def run_pip(self, args: str, cwd: str = None) -> dict:
        python_exe = self._find_python()
        cmd = f'"{python_exe}" -m pip {args}'
        return self.run(cmd, cwd=cwd)

    @staticmethod
    def _find_python() -> str:
        for candidate in ["python", "py", "python3"]:
            try:
                r = subprocess.run(
                    [candidate, "--version"], capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0:
                    return candidate
            except Exception:
                continue
        return "python"
