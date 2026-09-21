import json
import time
from pathlib import Path
from typing import Optional
import config


class Memory:
    def __init__(self, memory_file: Path = None):
        self.file = memory_file or config.MEMORY_FILE
        self.data = {"sessions": []}
        self._load()

    def _load(self):
        if self.file.exists():
            try:
                self.data = json.loads(self.file.read_text(encoding="utf-8"))
            except Exception:
                self.data = {"sessions": []}
        if "sessions" not in self.data:
            self.data["sessions"] = []

    def _save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def start_session(self, goal: str) -> str:
        session_id = f"session_{int(time.time())}"
        session = {
            "id": session_id,
            "goal": goal,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "running",
            "plan": None,
            "steps": [],
            "errors": [],
            "fixes": [],
            "result": None,
            "iterations": 0,
        }
        self.data["sessions"].append(session)
        self._save()
        return session_id

    def set_plan(self, session_id: str, plan: dict):
        s = self._find(session_id)
        if s:
            s["plan"] = plan
            self._save()

    def add_step(self, session_id: str, kind: str, message: str, detail: dict = None):
        s = self._find(session_id)
        if s:
            s["steps"].append({
                "time": time.strftime("%H:%M:%S"),
                "kind": kind,
                "message": message,
                "detail": detail or {},
            })
            s["iterations"] = s.get("iterations", 0) + (1 if kind in ("execute", "code", "test", "debug") else 0)
            self._save()

    def add_error(self, session_id: str, step: str, error_msg: str):
        s = self._find(session_id)
        if s:
            s["errors"].append({
                "time": time.strftime("%H:%M:%S"),
                "step": step,
                "message": error_msg,
            })
            self._save()

    def add_fix(self, session_id: str, error_summary: str, fix_action: str, success: bool = True):
        s = self._find(session_id)
        if s:
            s["fixes"].append({
                "time": time.strftime("%H:%M:%S"),
                "error": error_summary,
                "action": fix_action,
                "success": success,
            })
            self._save()

    def finish(self, session_id: str, status: str, result: str):
        s = self._find(session_id)
        if s:
            s["status"] = status
            s["result"] = result
            s["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._save()

    def _find(self, session_id: str) -> Optional[dict]:
        for s in self.data["sessions"]:
            if s["id"] == session_id:
                return s
        return None

    def get_session(self, session_id: str) -> Optional[dict]:
        return self._find(session_id)

    def summary(self, session_id: str) -> str:
        s = self._find(session_id)
        if not s:
            return "Oturum bulunamadi."
        lines = [
            f"=== OTURUM OZETI ===",
            f"Hedef: {s['goal']}",
            f"Durum: {s['status']}",
            f"Baslangic: {s['created_at']}",
            f"Adim sayisi: {len(s['steps'])}",
            f"Hata sayisi: {len(s['errors'])}",
            f"Duzeltme sayisi: {len(s['fixes'])}",
        ]
        if s.get("result"):
            lines.append(f"Sonuc: {s['result']}")
        return "\n".join(lines)
