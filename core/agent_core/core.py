"""REIS_AGENT_CORE — the unified autonomous orchestrator.

This is the Cursor-independent brain that every front-end (Telegram, web
console, CLI) calls. It runs one canonical loop and emits progress events:

    UNDERSTAND -> INTENT -> (CHAT | CAPABILITY | SELF | AGENT) -> VERIFY -> REPORT

Design goals from the REIS AI spec:
  * One entry point (`run`) shared by all interfaces.
  * Real execution via the existing tools (no fake success).
  * A verification gate: a task only "succeeds" when an action was executed,
    a test actually ran, and that test passed.
  * Reuses the already-real ReisMaxAgent (executor, tools, memory) instead of
    duplicating logic.
"""
from __future__ import annotations

import re
from typing import Any, Optional

import config
from core.agent.loop import ReisMaxAgent
from core.agent_core.capabilities import CapabilityRegistry
from core.agent_core.error_memory import ErrorMemory
from core.agent_core.events import (
    CHAT,
    CODE,
    DEBUG,
    EXECUTE,
    EventBus,
    EventSink,
    HEAL,
    INTENT,
    PLAN,
    REPORT,
    SECURITY,
    TEST,
    UNDERSTAND,
    VERIFY,
)
from core.agent_core.retry import RetryEngine, RetryPolicy
from core.agent_core.tasks import (
    STATUS_BLOCKED,
    STATUS_COMPLETED,
    TaskLedger,
    evaluate_gate,
)
from core.evolution.intents import match_evolution_intent
from core.llm_client import OllamaClient
from core.memory import Memory

# Execution modes the core routes between.
MODE_CHAT = "chat"
MODE_AGENT = "agent"
MODE_CAPABILITY = "capability"
MODE_SELF = "self"
MODE_STATUS = "status"

# Modes that run as long background tasks (stream progress); others reply once.
BACKGROUND_MODES = {MODE_AGENT, MODE_SELF}

# Free-text triggers asking about an existing task's status.
_STATUS_TRIGGERS = (
    "görev ne durumda",
    "gorev ne durumda",
    "görev durumu",
    "gorev durumu",
    "task durumu",
    "task status",
    "son görev",
    "son gorev",
    "hangi durumda",
    "görev nerede",
    "gorev nerede",
)

# Capabilities a real engineering task cannot run without.
_REQUIRED_FOR_AGENT = ("python", "filesystem", "terminal", "ollama_server")

# Free-text triggers that mean "tell me what you can do / your status".
_CAPABILITY_TRIGGERS = (
    "yeteneklerin",
    "neler yapabilirsin",
    "ne yapabilirsin",
    "capabilities",
    "capability",
    "araçların",
    "araclarin",
    "hangi araç",
    "hangi arac",
    "sistem durumu",
    "kapasiten",
)

# Intent categories that imply real engineering work (agent mode).
_AGENT_INTENTS = {
    "CODING",
    "PROJECT_TASK",
    "TASK",
    "DEBUG",
    "DEPLOYMENT",
    "FILE_OPERATION",
    "SYSTEM_OPERATION",
    "AUTOMATION",
}

# Strong verbs that clearly request execution (matched as substrings so they
# survive punctuation the intent tokenizer misses, e.g. "oluştur:").
_STRONG_VERBS = (
    "oluştur",
    "olustur",
    "kodla",
    "geliştir",
    "gelistir",
    "düzelt",
    "duzelt",
    "deploy",
    "çalıştır",
    "calistir",
    "implement",
    "refactor",
    "entegre",
    "kur ",
    "build",
    "create",
    " fix ",
)


class ReisAgentCore:
    """Interface-agnostic autonomous agent core."""

    def __init__(self, agent: Optional[ReisMaxAgent] = None, llm: Optional[OllamaClient] = None):
        self.agent = agent or ReisMaxAgent(llm)
        self.llm = self.agent.llm
        self.capabilities = CapabilityRegistry(self.llm)
        self.ledger = TaskLedger(self.agent.store)
        self.errors = ErrorMemory(self.agent.store)
        self.retry = RetryEngine(RetryPolicy(max_attempts=1, base_delay=0.5))

    # ── Routing ──────────────────────────────────────────────────────────
    def classify_mode(self, text: str) -> str:
        t = (text or "").strip().lower()
        if not t:
            return MODE_CHAT
        if any(k in t for k in _STATUS_TRIGGERS) or re.search(r"task_[0-9a-f]{6,}", t):
            return MODE_STATUS
        if any(k in t for k in _CAPABILITY_TRIGGERS):
            return MODE_CAPABILITY
        if match_evolution_intent(text):
            return MODE_SELF
        is_question = t.endswith("?")
        has_strong_verb = any(v in t for v in _STRONG_VERBS)
        intent = self.agent.intent.classify(text)
        # Agent mode when the user clearly wants execution: a strong build/fix
        # verb, or an engineering intent that is not phrased as a question.
        if has_strong_verb:
            return MODE_AGENT
        if intent.primary in _AGENT_INTENTS and not is_question:
            return MODE_AGENT
        return MODE_CHAT

    # ── Entry point ──────────────────────────────────────────────────────
    def run(
        self,
        request: str,
        on_event: Optional[EventSink] = None,
        approve: bool = False,
    ) -> dict[str, Any]:
        bus = EventBus(on_event)
        text = (request or "").strip()
        bus.emit(UNDERSTAND, text[:160])

        mode = self.classify_mode(text)
        intent = self.agent.intent.classify(text)
        bus.emit(INTENT, f"{intent.primary} → {mode}", intent=intent.primary, mode=mode)

        if mode == MODE_STATUS:
            return self._run_status(text, bus)
        if mode == MODE_CAPABILITY:
            return self._run_capability(bus)
        if mode == MODE_SELF:
            return self._run_self(text, bus)
        if mode == MODE_AGENT:
            return self._run_agent(text, bus, intent, approve)
        return self._run_chat(text, bus, intent)

    # ── Task status query ────────────────────────────────────────────────
    def _run_status(self, text: str, bus: EventBus) -> dict[str, Any]:
        m = re.search(r"task_[0-9a-f]{6,}", text.lower())
        task_id = m.group(0) if m else None
        message = self.ledger.status_text(task_id)
        bus.emit(REPORT, "durum raporu", level="success")
        return {
            "ok": True,
            "mode": MODE_STATUS,
            "message": message,
            "events": [e.to_dict() for e in bus.history],
        }

    def task_status(self, task_id: Optional[str] = None) -> str:
        return self.ledger.status_text(task_id)

    # ── Chat ─────────────────────────────────────────────────────────────
    def _run_chat(self, text: str, bus: EventBus, intent) -> dict[str, Any]:
        bus.emit(CHAT, "yanıt üretiliyor")
        self.agent.router.apply("CHAT")
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in list(self.agent.context.messages)[-8:]
        ]
        system = (
            "Sen REIS AI'sın: Telegram üzerinden kontrol edilen otonom bir yazılım "
            "mühendisliği ajanı. Doğal, samimi ve düzgün Türkçe konuş. Kısa soruya kısa "
            "cevap ver. Kullanıcı gerçek bir iş isterse (kod yaz, proje oluştur, hata "
            "düzelt) bunu otomatik yapabildiğini söyle."
        )
        messages = [{"role": "system", "content": system}] + history
        if not history or history[-1].get("content") != text:
            messages.append({"role": "user", "content": text})
        reply = self.llm.chat(messages, max_tokens=400, use_code_model=False)
        ok = bool(reply) and not reply.startswith("[LLM_HATA")
        self.agent.context.add_message("user", text)
        self.agent.context.add_message("assistant", reply)
        if getattr(config, "MEMORY_ENABLED", True):
            try:
                self.agent.store.add_conversation("user", text)
                self.agent.store.add_conversation("assistant", reply)
            except Exception:
                pass
        bus.emit(REPORT, "sohbet tamamlandı", level="success")
        return {
            "ok": ok,
            "mode": MODE_CHAT,
            "message": reply or "(boş yanıt)",
            "intent": intent.primary,
            "events": [e.to_dict() for e in bus.history],
        }

    # ── Capability report ────────────────────────────────────────────────
    def _run_capability(self, bus: EventBus) -> dict[str, Any]:
        bus.emit(SECURITY, "capability taraması")
        summary = self.capabilities.summary(force=True)
        report = self.capabilities.format_report(force=False)
        bus.emit(REPORT, "capability raporu hazır", level="success")
        return {
            "ok": True,
            "mode": MODE_CAPABILITY,
            "message": report,
            "data": summary,
            "events": [e.to_dict() for e in bus.history],
        }

    # ── Self-improvement / self-healing ──────────────────────────────────
    def _run_self(self, text: str, bus: EventBus) -> dict[str, Any]:
        bus.emit(EXECUTE, "self-evolution çalışıyor")
        try:
            self.agent.router.apply("REASONING")
            out = self.agent.evolution.run(text, resume=True)
            ok = bool(out.get("ok"))
            msg = out.get("message") or "Self-evolution tamamlandı."
        except Exception as e:  # never crash the loop
            ok, msg, out = False, f"Self-evolution hatası: {type(e).__name__}: {e}", {}
        bus.emit(REPORT, "self-evolution tamamlandı", level="success" if ok else "warn")
        return {
            "ok": ok,
            "mode": MODE_SELF,
            "message": msg,
            "data": out,
            "events": [e.to_dict() for e in bus.history],
        }

    # ── Real agent task ──────────────────────────────────────────────────
    def _run_agent(self, text: str, bus: EventBus, intent, approve: bool) -> dict[str, Any]:
        decision = self.agent.decision.decide(text, intent)
        if decision.get("needs_approval") and intent.primary == "DEPLOYMENT" and not approve:
            bus.emit(REPORT, "onay gerekli", level="warn")
            return {
                "ok": False,
                "mode": MODE_AGENT,
                "needs_approval": True,
                "message": "Bu işlem kritik (deployment). Onay verirsen uçtan uca tamamlarım.",
                "events": [e.to_dict() for e in bus.history],
            }

        task_id = self.ledger.open(text, intent=intent.primary, mode=MODE_AGENT)
        bus.emit(INTENT, f"task {task_id}", task_id=task_id)

        # Tool self-diagnostics + capability gap gate (section 6/7/20).
        gap = self.preflight(bus)
        if gap:
            self.ledger.block(task_id, f"Eksik capability: {', '.join(gap)}", missing=gap)
            bus.emit(REPORT, f"engellendi: eksik capability {', '.join(gap)}", level="error")
            return {
                "ok": False,
                "mode": MODE_AGENT,
                "task_id": task_id,
                "status": STATUS_BLOCKED,
                "message": (
                    "⛔ Görev başlatılamadı. Gerekli capability eksik: "
                    + ", ".join(gap)
                    + ". Bunu kurup tekrar denerim."
                ),
                "events": [e.to_dict() for e in bus.history],
            }

        self.agent.router.apply(decision.get("model_role", "coding"))
        bus.emit(PLAN, "adım adım plan çıkarılıyor")
        self.ledger.log(task_id, "plan", "plan çıkarılıyor")

        phase_map = {
            "plan": PLAN,
            "setup": EXECUTE,
            "execute": EXECUTE,
            "code": CODE,
            "test": TEST,
            "debug": DEBUG,
        }
        holder: dict[str, Any] = {"result": {}}

        def _emit_step(kind: str, msg: str) -> None:
            phase = phase_map.get(kind, EXECUTE)
            bus.emit(phase, (msg or "")[:180])
            self.ledger.log(task_id, phase, (msg or "")[:180])

        def primary() -> dict[str, Any]:
            memory = Memory()
            original_add_step = memory.add_step

            def hooked_add_step(sid, kind, msg, detail=None):
                original_add_step(sid, kind, msg, detail)
                _emit_step(kind, msg)

            memory.add_step = hooked_add_step  # type: ignore[method-assign]
            try:
                res = self.agent.executor.run(text, memory)
            finally:
                memory.add_step = original_add_step  # type: ignore[method-assign]
            holder["result"] = res
            return {"ok": self.verify(res)["ok"], "result": res}

        def alternative() -> dict[str, Any]:
            # Autonomous retry via an alternative strategy: re-run the
            # tester/debugger loop on the produced project once.
            res = holder.get("result") or {}
            pdir = res.get("project_dir")
            if not pdir:
                return {"ok": False}
            bus.emit(HEAL, "alternatif düzeltme deneniyor")
            self.ledger.log(task_id, HEAL, "alternatif düzeltme")
            from core.debugger import Debugger
            from core.tester import Tester

            tester = Tester()
            test = tester.detect_and_run(pdir)
            if not test.get("success"):
                # Skip a fix we already know fails for this error signature.
                err_text = (test.get("stderr") or "") + (test.get("stdout") or "")
                mem = Memory()
                sid = mem.start_session("alt-fix")
                Debugger(self.llm).auto_fix(sid, mem, pdir, test)
                test = tester.detect_and_run(pdir)
                if not test.get("success"):
                    self.errors.record(err_text, fix="tester+debugger auto_fix", success=False)
            res["final_test"] = test
            holder["result"] = res
            return {"ok": bool(test.get("success")), "result": res}

        def _on_attempt(attempt) -> None:
            self.ledger.set_retry(task_id, attempt.index)

        try:
            self.retry.run([("primary", primary), ("alternative", alternative)], on_attempt=_on_attempt)
        except Exception as e:
            bus.emit(REPORT, f"yürütme hatası: {e}", level="error")
            self.ledger.finalize(task_id, {"execution": False}, {"reason": str(e)}, message=str(e))
            return {
                "ok": False,
                "mode": MODE_AGENT,
                "task_id": task_id,
                "message": f"Görev sırasında hata: {type(e).__name__}: {e}",
                "events": [e.to_dict() for e in bus.history],
            }

        result = holder.get("result") or {}
        verification = self.verify(result)
        bus.emit(
            VERIFY,
            "doğrulandı" if verification["ok"] else verification["reason"],
            level="success" if verification["ok"] else "warn",
            **verification,
        )

        pdir = result.get("project_dir")
        if pdir:
            try:
                from pathlib import Path

                self.agent.context.set_project(pdir)
                self.agent.store.upsert_project(Path(pdir).name, pdir, technology="python")
            except Exception:
                pass

        # FINAL VERIFICATION GATE (section 21).
        checklist = {
            "execution": verification["executed"],
            "tests": verification["ran_test"],
            "verification": verification["test_passed"],
            "health": verification["ok"],
        }
        gate = self.ledger.finalize(task_id, checklist, verification, message=verification["reason"])
        status = gate["status"]

        if status != STATUS_COMPLETED:
            ft = result.get("final_test") or {}
            err_text = (ft.get("stderr") or "") + (ft.get("stdout") or "")
            if err_text.strip():
                self.errors.record(err_text, fix="executor loop", success=False, project=pdir)

        bus.emit(
            REPORT,
            "tamamlandı" if status == STATUS_COMPLETED else "başarısız/kısmi",
            level="success" if status == STATUS_COMPLETED else "warn",
        )
        return {
            "ok": status == STATUS_COMPLETED,
            "mode": MODE_AGENT,
            "task_id": task_id,
            "status": status,
            "message": self._format_agent_report(text, result, verification, task_id, checklist),
            "data": result,
            "verification": verification,
            "checklist": checklist,
            "events": [e.to_dict() for e in bus.history],
        }

    # ── Tool self-diagnostics / capability gap gate ──────────────────────
    def preflight(self, bus: EventBus) -> list[str]:
        bus.emit(SECURITY, "tool self-diagnostics")
        caps = self.capabilities.scan(force=True)
        gap = [name for name in _REQUIRED_FOR_AGENT if not caps.get(name) or not caps[name].available]
        return gap

    # ── NO FAKE SUCCESS: verification gate ───────────────────────────────
    @staticmethod
    def verify(result: dict[str, Any]) -> dict[str, Any]:
        """A task truly succeeds only if it executed AND a test ran AND passed."""
        final_test = result.get("final_test") or {}
        executed = bool(result.get("project_dir"))
        ran_test = bool(final_test.get("ran_test"))
        test_passed = bool(final_test.get("success"))
        ok = executed and ran_test and test_passed
        if not executed:
            reason = "Hiçbir işlem yürütülmedi"
        elif not ran_test:
            reason = "Test çalıştırılmadı"
        elif not test_passed:
            reason = "Testler geçmedi"
        else:
            reason = "Yürütüldü, test edildi ve doğrulandı"
        return {
            "ok": ok,
            "executed": executed,
            "ran_test": ran_test,
            "test_passed": test_passed,
            "reason": reason,
            "strategy": final_test.get("strategy"),
        }

    @staticmethod
    def _format_agent_report(
        goal: str,
        result: dict[str, Any],
        verification: dict[str, Any],
        task_id: str | None = None,
        checklist: dict[str, bool] | None = None,
    ) -> str:
        pdir = result.get("project_dir") or "-"
        ft = result.get("final_test") or {}
        head = "🟢 Görev tamamlandı" if verification["ok"] else "🔴 Görev başarısız"
        lines = [head]
        if task_id:
            lines.append(f"🆔 {task_id}")
        lines.append(f"• Görev: {goal[:120]}")
        lines.append(f"• Proje: {pdir}")
        if checklist:
            marks = "  ".join(
                f"{'✅' if checklist.get(k) else '❌'} {k}" for k in ("execution", "tests", "verification")
            )
            lines.append(f"• Kapı: {marks}")
        lines.append(f"• Doğrulama: {verification['reason']}")
        if verification.get("strategy"):
            lines.append(f"• Test yöntemi: {verification['strategy']}")
        out = (ft.get("stdout") or "").strip()
        if out:
            lines.append("• Çıktı: " + out[-250:])
        if not verification["ok"]:
            err = (ft.get("stderr") or "").strip()
            if err:
                lines.append("• Hata: " + err[-250:])
        return "\n".join(lines)
