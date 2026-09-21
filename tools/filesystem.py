import os
import re
import shutil
from pathlib import Path
from typing import Optional, List
import config


class FileSystemTool:
    def __init__(self):
        self.safe_roots = [Path(r).resolve() for r in config.SAFE_ROOTS]
        self.dangerous_patterns = [
            re.compile(p, re.IGNORECASE) for p in config.DANGEROUS_PATTERNS
        ]

    def _is_safe_path(self, target_path: str) -> tuple[bool, str]:
        try:
            p = Path(target_path).resolve()
        except Exception as e:
            return False, f"Gecersiz yol: {e}"

        str_path = str(p)
        for pat in self.dangerous_patterns:
            if pat.search(str_path):
                return False, f"Korunan yol: {str_path}"

        in_safe = False
        for root in self.safe_roots:
            try:
                p.relative_to(root)
                in_safe = True
                break
            except ValueError:
                continue

        if not in_safe:
            workspace_root = config.WORKSPACE_DIR.resolve()
            try:
                p.relative_to(workspace_root.parent.resolve())
                return True, "OK (proje icinde)"
            except ValueError:
                return False, f"Yol guvenli alan disinda: {str_path}\n  Guvenli alanlar: {[str(r) for r in self.safe_roots]}"

        return True, "OK"

    def mkdir(self, path: str, exist_ok: bool = True) -> dict:
        safe, reason = self._is_safe_path(path)
        if not safe:
            return {"success": False, "error": reason}
        try:
            Path(path).mkdir(parents=True, exist_ok=exist_ok)
            return {"success": True, "path": str(Path(path).resolve())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, path: str, content: str) -> dict:
        safe, reason = self._is_safe_path(path)
        if not safe:
            return {"success": False, "error": reason}
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"success": True, "path": str(p.resolve()), "bytes": len(content.encode("utf-8"))}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, path: str, limit_lines: int = 500) -> dict:
        safe, reason = self._is_safe_path(path)
        if not safe:
            return {"success": False, "error": reason}
        try:
            p = Path(path)
            if not p.is_file():
                return {"success": False, "error": f"Dosya bulunamadi: {path}"}
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            if len(lines) > limit_lines:
                text = "\n".join(lines[:limit_lines]) + f"\n\n... [truncated: total {len(lines)} lines]"
            return {"success": True, "content": text, "path": str(p.resolve())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def edit_file(self, path: str, old_str: str, new_str: str, replace_all: bool = False) -> dict:
        r = self.read_file(path)
        if not r["success"]:
            return r
        content = r["content"]
        if old_str not in content:
            return {"success": False, "error": "Eski metin dosyada bulunamadi. Degisiklik yapilamadi."}
        if replace_all:
            new_content = content.replace(old_str, new_str)
        else:
            new_content = content.replace(old_str, new_str, 1)
        return self.write_file(path, new_content)

    def update_file(self, path: str, old_str: str, new_str: str, replace_all: bool = True) -> dict:
        return self.edit_file(path, old_str, new_str, replace_all=replace_all)

    def delete_file(self, path: str) -> dict:
        safe, reason = self._is_safe_path(path)
        if not safe:
            return {"success": False, "error": reason}
        try:
            p = Path(path)
            if p.is_file():
                p.unlink()
                return {"success": True, "deleted": str(p.resolve())}
            elif p.is_dir():
                return {"success": False, "error": "Klasor silme icin delete_dir() kullanin."}
            return {"success": False, "error": "Hedef bulunamadi."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_dir(self, path: str = None, depth: int = 2) -> dict:
        if path is None:
            path = str(config.WORKSPACE_DIR)
        safe, reason = self._is_safe_path(path)
        if not safe:
            return {"success": False, "error": reason}
        try:
            base = Path(path)
            result = []
            current_depth = 0
            for root, dirs, files in os.walk(str(base)):
                level = root[len(str(base)):].count(os.sep)
                if level > depth:
                    dirs[:] = []
                    continue
                indent = "  " * level
                result.append(f"{indent}{os.path.basename(root)}/")
                sub_indent = "  " * (level + 1)
                for f in files:
                    result.append(f"{sub_indent}{f}")
            return {"success": True, "tree": "\n".join(result), "path": str(base.resolve())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_project_dir(self, project_name: str) -> dict:
        project_dir = config.WORKSPACE_DIR / project_name
        safe, reason = self._is_safe_path(str(project_dir))
        if not safe:
            return {"success": False, "error": reason}
        try:
            project_dir.mkdir(parents=True, exist_ok=True)
            return {"success": True, "path": str(project_dir.resolve())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_path(self, src: str, dst: str) -> dict:
        safe_s, reason_s = self._is_safe_path(src)
        safe_d, reason_d = self._is_safe_path(dst)
        if not safe_s:
            return {"success": False, "error": reason_s}
        if not safe_d:
            return {"success": False, "error": reason_d}
        try:
            s, d = Path(src), Path(dst)
            d.parent.mkdir(parents=True, exist_ok=True)
            if s.is_dir():
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
            return {"success": True, "src": str(s.resolve()), "dst": str(d.resolve())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_path(self, src: str, dst: str) -> dict:
        safe_s, reason_s = self._is_safe_path(src)
        safe_d, reason_d = self._is_safe_path(dst)
        if not safe_s:
            return {"success": False, "error": reason_s}
        if not safe_d:
            return {"success": False, "error": reason_d}
        try:
            d = Path(dst)
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return {"success": True, "src": src, "dst": str(d.resolve())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_path(self, src: str, new_name: str) -> dict:
        p = Path(src)
        return self.move_path(src, str(p.with_name(new_name)))

    def search_files(self, root: str, pattern: str, max_hits: int = 50) -> dict:
        safe, reason = self._is_safe_path(root)
        if not safe:
            return {"success": False, "error": reason}
        hits = []
        base = Path(root)
        try:
            for p in base.rglob("*"):
                if p.is_file() and pattern.lower() in p.name.lower():
                    hits.append(str(p))
                    if len(hits) >= max_hits:
                        break
            return {"success": True, "hits": hits, "count": len(hits)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def compare_files(self, a: str, b: str) -> dict:
        ra, rb = self.read_file(a), self.read_file(b)
        if not ra.get("success"):
            return ra
        if not rb.get("success"):
            return rb
        same = ra["content"] == rb["content"]
        return {"success": True, "same": same, "a_bytes": len(ra["content"]), "b_bytes": len(rb["content"])}

    def delete_dir(self, path: str) -> dict:
        safe, reason = self._is_safe_path(path)
        if not safe:
            return {"success": False, "error": reason}
        try:
            p = Path(path)
            if p.is_dir():
                import shutil as _shutil
                _shutil.rmtree(p, ignore_errors=False)
                return {"success": True, "deleted": str(p.resolve())}
            return {"success": False, "error": "Klasor bulunamadi."}
        except Exception as e:
            return {"success": False, "error": str(e)}
