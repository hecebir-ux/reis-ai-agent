from __future__ import annotations

from pathlib import Path

import config
from core.context.engine import ContextEngine
from core.decision import DecisionEngine
from core.executor import Executor
from core.intent.engine import IntentEngine
from core.llm_client import OllamaClient
from core.logutil import log_system, log_user
from core.memory import Memory
from core.model_router.router import ModelRouter
from core.recovery import RecoveryStore
from core.security import redact
from core.task_manager.manager import TaskManager
from database.store import SQLiteStore
from tools.filesystem import FileSystemTool
from tools.git_tool import GitTool
from tools.project_tool import ProjectAnalyzer
from tools.web_tool import WebTool
from core.evolution.intents import match_evolution_intent
from core.evolution.loop import EvolutionLoop


class ReisMaxAgent:
    def __init__(self, llm: OllamaClient | None = None):
        self.llm = llm or OllamaClient()
        self.router = ModelRouter(self.llm)
        self.intent = IntentEngine()
        self.context = ContextEngine()
        self.decision = DecisionEngine()
        self.store = SQLiteStore()
        self.tasks = TaskManager(self.store)
        self.json_memory = Memory()
        self.executor = Executor(self.llm)
        self.fs = FileSystemTool()
        self.git = GitTool()
        self.projects = ProjectAnalyzer()
        self.web = WebTool()
        self.recovery = RecoveryStore()
        self.evolution = EvolutionLoop(self)
        self.last_task_id: str | None = None
        self.paused = False
        self.stop_requested = False

    def handle(self, user_text: str) -> dict:
        if self.stop_requested:
            return {"ok": False, "kind": "control", "message": "Durduruldu. /resume ile devam."}
        text = (user_text or "").strip()
        evo = match_evolution_intent(text)
        if evo:
            self.router.apply("REASONING")
            out = self.evolution.run(text, resume=True)
            self.context.add_message("user", text)
            self.context.add_message("assistant", out.get("message") or "")
            if config.MEMORY_ENABLED:
                self.store.add_conversation("user", text)
                self.store.add_conversation("assistant", out.get("message") or "")
            return out

        intent = self.intent.classify(text)
        decision = self.decision.decide(text, intent)
        self.context.add_message("user", text)
        if config.MEMORY_ENABLED:
            self.store.add_conversation("user", text)
            self.store.add_memory("SHORT_TERM", text, key="last_user")

        if decision["needs_approval"] and intent.primary in {"DEPLOYMENT"}:
            return {
                "ok": False,
                "kind": "approval",
                "message": "Bu işlem kritik (deployment). Onay olmadan production'a çıkmam.",
                "intent": intent.primary,
                "risk": decision["risk"],
            }

        self.router.apply(decision["model_role"])

        if intent.primary in {"CODING", "PROJECT_TASK", "TASK"} and any(
            k in text.lower() for k in ("yap", "oluştur", "olustur", "yaz", "build", "create", "kodla", "geliştir", "gelistir")
        ):
            return self._run_project(text, intent.primary)

        if intent.primary == "DEBUG" and ("düzelt" in text.lower() or "duzelt" in text.lower()):
            if self.context.active_project:
                return self._debug_project(self.context.active_project, text)
            return {"ok": False, "kind": "chat", "message": "Aktif proje yok. Önce bir proje oluştur."}

        if intent.primary == "ANALYSIS" or "analiz" in text.lower():
            target = self.context.active_project or str(config.WORKSPACE_DIR)
            analysis = self.projects.analyze(target)
            return {"ok": analysis.get("success"), "kind": "analysis", "data": analysis, "message": self._fmt_analysis(analysis)}

        if intent.primary == "RESEARCH" and config.WEB_ENABLED:
            return self._research(text)

        if "git" in text.lower() and any(k in text.lower() for k in ("durum", "status", "log")):
            r = self.git.status()
            return {"ok": r.get("success"), "kind": "git", "message": r.get("stdout") or r.get("stderr")}

        return self._chat(text, intent)

    def _chat(self, text: str, intent) -> dict:
        import sys

        self.router.apply("CHAT")
        history = [{"role": m["role"], "content": m["content"]} for m in list(self.context.messages)[-10:]]
        system = (
            "Sen REIS AI MAX'sin. Yerel Ollama ile çalışan otonom asistan. "
            "Doğal, düzgün Türkçe konuş. Kısa soruya kısa, detay gerekince detaylı cevap ver. "
            "Bağlam:\n" + self.context.compact()
        )
        messages = [{"role": "system", "content": system}] + history
        if not history or history[-1]["content"] != text:
            messages.append({"role": "user", "content": text})
        chunks: list[str] = []

        def on_token(tok: str) -> None:
            chunks.append(tok)
            sys.stdout.write(tok)
            sys.stdout.flush()

        print("REIS AI: ", end="", flush=True)
        reply = self.llm.chat_stream(messages, max_tokens=500, on_token=on_token, use_code_model=False)
        print("", flush=True)
        if not reply or reply.startswith("[LLM_HATA"):
            ok = False
        else:
            ok = True
        self.context.add_message("assistant", reply)
        if config.MEMORY_ENABLED:
            self.store.add_conversation("assistant", reply)
        return {"ok": ok, "kind": "chat", "message": reply, "intent": intent.primary, "streamed": True}

    def _run_project(self, goal: str, primary: str) -> dict:
        task = self.tasks.create(goal, description=primary, priority=7)
        self.last_task_id = task["id"]
        self.context.set_task(task)
        self.recovery.save({"task_id": task["id"], "goal": goal, "step": "execute"})
        log_user(f"Görev başladı: {goal}")
        self.tasks.set_status(task["id"], "RUNNING", step="plan", progress=0.1)
        result = self.executor.run(goal, self.json_memory)
        ok = bool(result.get("ok"))
        pdir = result.get("project_dir")
        if pdir:
            self.context.set_project(pdir)
            self.store.upsert_project(Path(pdir).name, pdir, technology="python")
            self.context.remember_decision(f"Proje oluşturuldu: {pdir}")
        status = "COMPLETED" if ok else "FAILED"
        self.tasks.set_status(task["id"], status, step="validate", progress=1.0 if ok else 0.8)
        self.tasks.update(task["id"], result=result)
        self.recovery.save({"task_id": task["id"], "goal": goal, "step": status.lower(), "project": pdir})
        msg = self._user_result(goal, result)
        log_user(msg)
        return {"ok": ok, "kind": "project", "message": msg, "data": result, "task_id": task["id"]}

    def _debug_project(self, project_dir: str, text: str) -> dict:
        from core.debugger import Debugger
        from core.tester import Tester
        tester = Tester()
        test_result = tester.detect_and_run(project_dir)
        if test_result.get("success"):
            return {"ok": True, "kind": "debug", "message": "Testler zaten geçiyor.", "data": test_result}
        sid = self.json_memory.start_session(f"debug:{text}")
        dbg = Debugger(self.llm)
        fix = dbg.auto_fix(sid, self.json_memory, project_dir, test_result)
        ok = bool(fix.get("fixed"))
        msg = "Hata düzeltildi ve testler geçti." if ok else f"Düzeltilemedi: {fix.get('reason') or 'limit'}"
        return {"ok": ok, "kind": "debug", "message": msg, "data": fix}

    def _research(self, text: str) -> dict:
        # Prefer official docs URLs when the query is python-related
        url = "https://docs.python.org/3/"
        if "flask" in text.lower():
            url = "https://flask.palletsprojects.com/en/stable/"
        page = self.web.fetch_readable(url, max_chars=2500)
        summary = page.get("readable_text", page.get("error", ""))[:1200]
        return {"ok": bool(page.get("success")), "kind": "research", "message": summary, "data": {"url": url}}

    def _fmt_analysis(self, a: dict) -> str:
        if not a.get("success"):
            return a.get("error") or "Analiz başarısız"
        return (
            f"Proje: {a.get('path')}\n"
            f"Framework: {a.get('framework')} | giriş: {a.get('entry_point')}\n"
            f"Dosya: {a.get('file_count')} | test: {len(a.get('tests') or [])}\n"
            f"Bağımlılık: {', '.join((a.get('dependencies') or [])[:8]) or '-'}"
        )

    def _user_result(self, goal: str, result: dict) -> str:
        status = result.get("status")
        pdir = result.get("project_dir") or ""
        if result.get("ok") and status == "success":
            return f"Hazır. Testler geçti.\nProje: {pdir}"
        if pdir:
            return f"Kısmen tamamlandı ({status}).\nProje: {pdir}\nDetay log: memory/"
        return f"Görev tamamlanamadı: {redact(str(result.get('error') or status))}"
