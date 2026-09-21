from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.filesystem import FileSystemTool


class DocumentEngine:
    def __init__(self):
        self.fs = FileSystemTool()

    def read(self, path: str) -> dict:
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix in {".txt", ".md", ".json", ".csv", ".py", ".yml", ".yaml"}:
            if suffix == ".json":
                r = self.fs.read_file(path)
                if not r.get("success"):
                    return r
                try:
                    r["parsed"] = json.loads(r["content"])
                except Exception as e:
                    r["parse_error"] = str(e)
                return r
            if suffix == ".csv":
                r = self.fs.read_file(path, limit_lines=200)
                if r.get("success"):
                    r["rows"] = list(csv.reader(r["content"].splitlines()))[:50]
                return r
            return self.fs.read_file(path)
        if suffix == ".pdf":
            try:
                import pypdf  # type: ignore
                reader = pypdf.PdfReader(str(p))
                text = "\n".join((page.extract_text() or "") for page in reader.pages[:20])
                return {"success": True, "content": text, "path": str(p)}
            except Exception as e:
                return {"success": False, "error": f"PDF okuyucu yok veya hata: {e}"}
        if suffix in {".docx", ".xlsx"}:
            return {"success": False, "error": f"{suffix} için opsiyonel paket gerekli (python-docx / openpyxl)."}
        return self.fs.read_file(path)

    def write_markdown(self, path: str, title: str, body: str) -> dict:
        content = f"# {title}\n\n{body.strip()}\n"
        return self.fs.write_file(path, content)
