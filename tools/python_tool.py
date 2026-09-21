from pathlib import Path
from typing import Optional
from tools.terminal import TerminalTool
from tools.filesystem import FileSystemTool
import config


class PythonTool:
    def __init__(self):
        self.terminal = TerminalTool()
        self.fs = FileSystemTool()

    def create_script(self, path: str, code: str) -> dict:
        return self.fs.write_file(path, code)

    def run_script(self, script_path: str, args: str = "", cwd: str = None) -> dict:
        p = Path(script_path)
        if not p.is_absolute():
            p = config.WORKSPACE_DIR / p
        if not p.exists():
            return {"success": False, "error": f"Script bulunamadi: {p}"}
        working_dir = cwd if cwd else str(p.parent)
        return self.terminal.run_python(str(p), args=args, cwd=working_dir)

    def install_package(self, package: str, upgrade: bool = False) -> dict:
        args = f"install {package}"
        if upgrade:
            args += " --upgrade"
        return self.terminal.run_pip(args)

    def install_requirements(self, requirements_path: str) -> dict:
        p = Path(requirements_path)
        if not p.is_absolute():
            p = config.WORKSPACE_DIR / p
        if not p.exists():
            return {"success": False, "error": f"requirements.txt bulunamadi: {p}"}
        return self.terminal.run_pip(f'install -r "{p}"')

    def check_package(self, package: str) -> dict:
        result = self.terminal.run_pip(f"show {package}")
        if result["exit_code"] == 0:
            return {"success": True, "installed": True, "info": result["stdout"]}
        return {"success": True, "installed": False, "info": result["stderr"]}

    def create_requirements(self, dir_path: str, packages: list[str]) -> dict:
        content = "\n".join(packages) + "\n"
        p = Path(dir_path) / "requirements.txt"
        return self.fs.write_file(str(p), content)

    def analyze_python_error(self, stderr: str) -> dict:
        lines = stderr.strip().splitlines()
        info = {
            "error_type": None,
            "error_message": None,
            "file": None,
            "line": None,
            "traceback": [],
        }
        in_trace = False
        for line in lines:
            line_s = line.rstrip()
            if "Traceback" in line_s:
                in_trace = True
                continue
            if in_trace:
                info["traceback"].append(line_s)
                m_file_line = None
                if 'File "' in line_s:
                    start = line_s.find('File "') + 6
                    end = line_s.find('", line ', start)
                    if start > 6 and end > start:
                        info["file"] = line_s[start:end]
                        line_part = line_s[end:]
                        num_match = ""
                        for ch in line_part:
                            if ch.isdigit():
                                num_match += ch
                            elif num_match:
                                break
                        if num_match:
                            info["line"] = int(num_match)
                if line_s and not line_s.startswith(" ") and not line_s.startswith("\t") and ":" in line_s:
                    parts = line_s.split(":", 1)
                    if parts[0] and all(c.isalnum() or c == "_" or c == "." for c in parts[0]):
                        info["error_type"] = parts[0]
                        info["error_message"] = parts[1].strip()
                        in_trace = False
        return info
