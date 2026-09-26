#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REIS Agent Core — deterministic unit/integration tests (no LLM required)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.chdir(str(HERE))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    ok = bool(cond)
    mark = "[OK]" if ok else "[HATA]"
    print(f"{mark} {name}" + (f" — {detail[:200]}" if detail else ""))
    RESULTS.append((name, ok, detail))
    return ok


def test_capabilities() -> None:
    from core.agent_core.capabilities import CapabilityRegistry

    reg = CapabilityRegistry()
    caps = reg.scan(force=True)
    check("Capability: python available", caps["python"].available, caps["python"].version)
    check("Capability: git available", caps["git"].available, caps["git"].version)
    check("Capability: filesystem+terminal core", caps["filesystem"].available and caps["terminal"].available)
    summary = reg.summary()
    check("Capability summary has counts", summary["available_count"] > 0 and summary["count"] > 0,
          f"{summary['available_count']}/{summary['count']}")
    # gaps() must only ever list required (non-optional) missing capabilities
    for g in reg.gaps():
        check(f"Gap '{g}' is genuinely required+missing", not caps[g].available and not caps[g].optional)
    check("format_report renders", "Capability Registry" in reg.format_report())


def test_mode_routing() -> None:
    from core.agent_core.core import (
        MODE_AGENT,
        MODE_CAPABILITY,
        MODE_CHAT,
        MODE_SELF,
        ReisAgentCore,
    )

    core = ReisAgentCore()  # constructs real agent but makes no LLM calls here
    cases = [
        ("Merhaba, nasılsın?", MODE_CHAT),
        ("Python'da async nedir?", MODE_CHAT),
        ("Bir python hesap makinesi uygulaması oluştur", MODE_AGENT),
        ("Şu hatayı düzelt", MODE_AGENT),
        ("Yeteneklerin neler?", MODE_CAPABILITY),
        ("Kendini geliştir", MODE_SELF),
    ]
    for text, expected in cases:
        got = core.classify_mode(text)
        check(f"Mode('{text[:30]}') == {expected}", got == expected, f"got={got}")


def test_verify_gate() -> None:
    from core.agent_core.core import ReisAgentCore

    # Real success: executed + ran a test + passed
    good = {"project_dir": "/tmp/x", "final_test": {"ran_test": True, "success": True, "strategy": "run app.py"}}
    v = ReisAgentCore.verify(good)
    check("verify: real success is ok", v["ok"], v["reason"])

    # Fake success blocked: code written but no test executed
    no_test = {"project_dir": "/tmp/x", "final_test": {"ran_test": False, "success": True}}
    v = ReisAgentCore.verify(no_test)
    check("verify: no-test is NOT ok", not v["ok"], v["reason"])

    # Test ran but failed
    failed = {"project_dir": "/tmp/x", "final_test": {"ran_test": True, "success": False}}
    v = ReisAgentCore.verify(failed)
    check("verify: failed test is NOT ok", not v["ok"], v["reason"])

    # Nothing executed at all
    nothing = {"final_test": {}}
    v = ReisAgentCore.verify(nothing)
    check("verify: no execution is NOT ok", not v["ok"], v["reason"])


def test_progress_renderer() -> None:
    from core.agent_core.events import AgentEvent, EXECUTE, PLAN, REPORT
    from core.agent_core.telegram_runtime import ProgressRenderer

    r = ProgressRenderer()
    r.update(AgentEvent(PLAN, "plan çıkarılıyor"))
    r.update(AgentEvent(EXECUTE, "adım 1"))
    board1 = r.update(AgentEvent(EXECUTE, "adım 2"))  # overwrites the same phase line
    check("Renderer keeps one line per phase", board1.count("Uygulanıyor") == 1, board1.replace("\n", " | "))
    final = r.update(AgentEvent(REPORT, "bitti", level="success"))
    check("Renderer shows report line", "Tamamlandı" in final)


def test_telegram_bridge() -> None:
    from core.agent_core.events import EventBus, EXECUTE, PLAN, REPORT, TEST, VERIFY
    from core.agent_core.telegram_runtime import TelegramAgentBridge

    class FakeCore:
        def __init__(self, mode, events):
            self._mode = mode
            self._events = events

        def classify_mode(self, text):
            return self._mode

        def run(self, text, on_event=None, approve=False):
            bus = EventBus(on_event)
            for phase, msg in self._events:
                bus.emit(phase, msg)
            return {"ok": True, "mode": self._mode, "message": "RAPOR: tamam",
                    "events": [e.to_dict() for e in bus.history]}

    class FakeTransport:
        def __init__(self):
            self.sent: list[tuple[int, int, str]] = []
            self.edits: list[tuple[int, int, str]] = []
            self._id = 100

        def send(self, chat_id, text):
            self._id += 1
            self.sent.append((chat_id, self._id, text))
            return self._id

        def edit(self, chat_id, message_id, text):
            self.edits.append((chat_id, message_id, text))

    # Chat mode -> exactly one reply, no edits.
    t = FakeTransport()
    bridge = TelegramAgentBridge(FakeCore("chat", []), t.send, t.edit, run_async=False)
    bridge.handle(555, "selam")
    check("Bridge chat: single reply", len(t.sent) == 1 and len(t.edits) == 0, f"sent={len(t.sent)} edits={len(t.edits)}")

    # Agent task -> initial message + live edits + final report.
    t2 = FakeTransport()
    events = [(PLAN, "plan"), (EXECUTE, "adım 1"), (TEST, "test"), (VERIFY, "doğrulandı"), (REPORT, "tamam")]
    bridge2 = TelegramAgentBridge(FakeCore("agent", events), t2.send, t2.edit, run_async=False)
    bridge2.handle(777, "bir uygulama oluştur")
    check("Bridge task: initial + final message", len(t2.sent) >= 2, f"sent={len(t2.sent)}")
    check("Bridge task: progress edited live", len(t2.edits) >= 3, f"edits={len(t2.edits)}")
    check("Bridge task: single evolving message id", t2.edits and len({e[1] for e in t2.edits}) == 1)
    check("Bridge task: final board shows completion", any("Tamamlandı" in e[2] for e in t2.edits))


def main() -> int:
    print("=" * 70)
    print("  REIS AGENT CORE — TEST SÜİTİ")
    print("=" * 70)
    test_capabilities()
    test_mode_routing()
    test_verify_gate()
    test_progress_renderer()
    test_telegram_bridge()
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n  SONUÇ: {passed}/{total}")
    ok = passed == total
    print("  REIS AGENT CORE READY" if ok else "  BAŞARISIZ TEST VAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
