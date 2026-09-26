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

from typing import Any, Optional

import config
from core.agent.loop import ReisMaxAgent
from core.agent_core.capabilities import CapabilityRegistry
from core.agent_core.events import (
    CHAT,
    CODE,
    DEBUG,
    EXECUTE,
    EventBus,
    EventSink,
    INTENT,
    PLAN,
    REPORT,
    SECURITY,
    TEST,
    UNDERSTAND,
    VERIFY,
)
from core.evolution.intents import match_evolution_intent
from core.llm_client import OllamaClient
from core.memory import Memory

# Execution modes the core routes between.
MODE_CHAT = "chat"
MODE_AGENT = "agent"
MODE_CAPABILITY = "capability"
MODE_SELF = "self"

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

    # ── Routing ──────────────────────────────────────────────────────────
    def classify_mode(self, text: str) -> str:
        t = (text or "").strip().lower()
        if not t:
            return MODE_CHAT
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

        if mode == MODE_CAPABILITY:
            return self._run_capability(bus)
        if mode == MODE_SELF:
            return self._run_self(text, bus)
        if mode == MODE_AGENT:
            return self._run_agent(text, bus, intent, approve)
        return self._run_chat(text, bus, intent)

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

        self.agent.router.apply(decision.get("model_role", "coding"))
        bus.emit(PLAN, "adım adım plan çıkarılıyor")

        memory = Memory()
        phase_map = {
            "plan": PLAN,
            "setup": EXECUTE,
            "execute": EXECUTE,
            "code": CODE,
            "test": TEST,
            "debug": DEBUG,
        }
        original_add_step = memory.add_step

        def hooked_add_step(sid, kind, msg, detail=None):  # emit live progress
            original_add_step(sid, kind, msg, detail)
            bus.emit(phase_map.get(kind, EXECUTE), (msg or "")[:180])

        memory.add_step = hooked_add_step  # type: ignore[method-assign]
        try:
            result = self.agent.executor.run(text, memory)
        except Exception as e:
            bus.emit(REPORT, f"yürütme hatası: {e}", level="error")
            return {
                "ok": False,
                "mode": MODE_AGENT,
                "message": f"Görev sırasında hata: {type(e).__name__}: {e}",
                "events": [e.to_dict() for e in bus.history],
            }
        finally:
            memory.add_step = original_add_step  # type: ignore[method-assign]

        verification = self.verify(result)
        bus.emit(
            VERIFY,
            "doğrulandı" if verification["ok"] else verification["reason"],
            level="success" if verification["ok"] else "warn",
            **verification,
        )
        # Persist the project + task outcome through the existing agent plumbing.
        pdir = result.get("project_dir")
        if pdir:
            try:
                from pathlib import Path

                self.agent.context.set_project(pdir)
                self.agent.store.upsert_project(Path(pdir).name, pdir, technology="python")
            except Exception:
                pass

        bus.emit(
            REPORT,
            "tamamlandı" if verification["ok"] else "kısmen tamamlandı",
            level="success" if verification["ok"] else "warn",
        )
        return {
            "ok": verification["ok"],
            "mode": MODE_AGENT,
            "message": self._format_agent_report(text, result, verification),
            "data": result,
            "verification": verification,
            "events": [e.to_dict() for e in bus.history],
        }

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
    def _format_agent_report(goal: str, result: dict[str, Any], verification: dict[str, Any]) -> str:
        pdir = result.get("project_dir") or "-"
        ft = result.get("final_test") or {}
        head = "✅ Tamamlandı" if verification["ok"] else "⚠️ Kısmen tamamlandı"
        lines = [
            f"{head}",
            f"Görev: {goal}",
            f"Proje: {pdir}",
            f"Doğrulama: {verification['reason']}",
        ]
        if verification.get("strategy"):
            lines.append(f"Test yöntemi: {verification['strategy']}")
        out = (ft.get("stdout") or "").strip()
        if out:
            lines.append("Çıktı: " + out[-300:])
        if not verification["ok"]:
            err = (ft.get("stderr") or "").strip()
            if err:
                lines.append("Hata: " + err[-300:])
        return "\n".join(lines)
