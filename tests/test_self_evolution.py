#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-evolution V2 — syntax, import, unit, ollama, evolver, rollback, heal, router, diagnostics, web."""
from __future__ import annotations

import ast
import json
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.chdir(str(HERE))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from colorama import Fore, Style, init

init()

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    mark = f"{Fore.GREEN}[OK]{Style.RESET_ALL}" if cond else f"{Fore.RED}[HATA]{Style.RESET_ALL}"
    print(f"{mark} {name}")
    if detail:
        print(f"       {detail[:240]}")
    RESULTS.append((name, bool(cond), detail))
    return bool(cond)


def _syntax_modules() -> list[Path]:
    from core.evolution.scan_util import iter_project_py

    return [p for p in iter_project_py(HERE) if "core" in p.parts or p.name in {"main.py", "agent.py", "config.py"}]


def run() -> None:
    print(f"{Fore.CYAN}=== SELF-EVOLUTION TEST ==={Style.RESET_ALL}\n")

    import config
    from core.evolution.intents import match_evolution_intent
    from core.evolution.knowledge import KnowledgeMemory
    from core.evolution.loop import EvolutionLoop
    from core.evolution.project_mapper import ProjectMapper
    from core.evolution.safe_auto_update import UpdateLevel, classify_update, may_auto_apply
    from core.evolution.self_benchmark import SelfBenchmark
    from core.evolution.self_diagnostics import SelfDiagnostics
    from core.evolution.self_evolver import SelfEvolver
    from core.evolution.self_feature_builder import SelfFeatureBuilder
    from core.evolution.self_healing import SelfHealing, heuristic_fix, analyze_traceback
    from core.evolution.self_optimizer import SelfOptimizer
    from core.evolution.self_reviewer import SelfReviewer
    from core.evolution.self_tester import SelfTester
    from core.evolution.task_state import EvolutionState
    from core.evolution.web_research import WebResearchEngine
    from core.executor import Executor
    from core.llm_client import OllamaClient
    from core.model_router.router import ModelRouter

    # 1 syntax
    syn_ok = True
    syn_err = ""
    for p in _syntax_modules():
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            syn_ok = False
            syn_err = f"{p.name}: {e}"
            break
    check("1 Python syntax", syn_ok, syn_err)

    # 2 import
    imp = SelfTester().run_file_import(HERE / "core" / "evolution" / "loop.py")
    check("2 Import evolution.loop", bool(imp.get("ok")), imp.get("stderr") or "")

    # 3 unit: intents
    phrases = [
        ("Kendini geliştir.", "full_evolve"),
        ("Kendini analiz et.", "diagnose"),
        ("Daha hızlı cevap ver.", "faster"),
        ("Yazım hatalarını azalt.", "typos"),
        ("Dosya yönetimini geliştir.", "files"),
        ("Yeni bir özellik ekle.", "new_feature"),
        ("Bu hatayı çöz.", "fix_error"),
        ("Bu projeyi geliştir.", "improve_project"),
        ("Bilgisayarımı kontrol et.", "system_check"),
        ("Masaüstümü düzenle.", "desktop"),
        ("Bu projeyi kendin test et.", "self_test"),
        (
            "Kendini analiz et, eksiklerini bul, daha hızlı ve daha sağlam hale gel, gerekli özellikleri geliştir.",
            "full_evolve",
        ),
    ]
    intent_ok = True
    bad = ""
    for text, kind in phrases:
        got = match_evolution_intent(text)
        if not got or got.kind != kind:
            intent_ok = False
            bad = f"{text!r} -> {got.kind if got else None} expected {kind}"
            break
    check("3 Doğal dil intentleri", intent_ok, bad)

    # 4 ollama
    llm = OllamaClient()
    health = llm.health_check()
    check("4 Ollama connectivity", bool(health.get("ok")), str(health.get("error") or health.get("models", [])[:6]))

    # 5 executor
    ex = Executor(llm)
    check("5 Executor tools", all(hasattr(ex, n) for n in ("tester", "debugger", "python", "fs")))

    # 6 evolver commit
    sandbox = HERE / "tests" / "_evo_sandbox.py"
    sandbox.write_text("VALUE = 1\n", encoding="utf-8")
    evolver = SelfEvolver()
    applied = evolver.apply_change(sandbox, "VALUE = 2\n", reason="sandbox bump")
    check("6 Self-Evolver commit", bool(applied.get("ok")) and sandbox.read_text(encoding="utf-8") == "VALUE = 2\n", str(applied))

    # 7 rollback on syntax fail
    rolled = evolver.apply_change(sandbox, "def broken(\n", reason="bad syntax")
    still = sandbox.read_text(encoding="utf-8")
    check("7 Rollback (syntax)", (not rolled.get("ok")) and still == "VALUE = 2\n", str(rolled.get("status")))

    # 8 self-healing
    heal_file = HERE / "tests" / "_heal_sandbox.py"
    heal_file.write_text(
        "def add(a, b):\n    return a / b\n\ndef main():\n    return add(1, 0)\n",
        encoding="utf-8",
    )
    healed = SelfHealing().heal_source_file(heal_file)
    check("8 Self-Healing", bool(healed.get("ok")), str(healed.get("reason") or healed.get("attempts")))

    healer = SelfHealing()
    ok_run = healer.run(lambda: 1 + 1)
    fail_run = healer.run(lambda: 1 / 0)
    check("8b Heal run success+rollback", bool(ok_run.get("ok")) and fail_run.get("rolled_back") is True)

    tb = "Traceback:\n  File \"x.py\", line 3, in f\nZeroDivisionError: division by zero\n"
    cause = analyze_traceback(tb)
    check("8c Traceback root cause", cause.get("root_cause") == "division_by_zero")
    check("8d heuristic_fix", "b == 0" in (heuristic_fix("def add(a, b):\n    return a / b\n", cause, "ZeroDivisionError") or ""))

    # 9 model router
    router = ModelRouter(llm)
    coding = router.resolve("CODING")
    fast = router.resolve("FAST")
    analysis = router.resolve("ANALYSIS")
    vision = router.resolve("VISION")
    check(
        "9 Model Router",
        coding.get("model") is not None and fast.get("requested"),
        f"code={coding.get('model')} fast={fast.get('model')} analysis={analysis.get('model')} vis={vision.get('model')}",
    )
    if health.get("ok") and coding.get("model"):
        check("9b coding family", "coder" in str(coding.get("requested")).lower() or "qwen" in str(coding.get("model")).lower())
    else:
        check("9b coding family (ollama yok, skip-pass)", True, "skipped")

    # 10 diagnostics
    diag = SelfDiagnostics().scan()
    keys = {"problems", "missing_capabilities", "performance_issues", "security_issues", "test_gaps", "recommendations"}
    check("10 Diagnostics keys", keys.issubset(diag.keys()), str(list(diag.keys())))
    check("10b Diagnostics files", (diag.get("stats") or {}).get("python_files", 0) > 5)

    # 11 web fallback
    engine = WebResearchEngine()
    skip = engine.research("selam naber")
    check("11 Web local-first skip", bool(skip.get("skipped") or skip.get("ok")))
    old_web = config.WEB_ENABLED
    config.WEB_ENABLED = False
    forced = engine.research("güncel python api", force=True)
    config.WEB_ENABLED = old_web
    check("11b Web fallback no crash", forced.get("degraded") or forced.get("ok") or "WEB_ENABLED" in str(forced.get("error")))

    # extras: benchmark, optimizer, reviewer, state, policy, knowledge, mapper
    bench = SelfBenchmark()
    old = bench.measure(lambda: sum(range(1000)), rounds=2)
    new = bench.measure(lambda: sum(range(1000)), rounds=2)
    cmp = bench.compare(old, new, max_regression=2.0)
    check("Benchmark accept", bool(cmp.get("accept")))

    tips = SelfOptimizer().advise()
    check("Optimizer advise", isinstance(tips, list) and len(tips) >= 1)

    rev = SelfReviewer().review_source("def run():\n    return 1\n", "snippet.py")
    check("Reviewer syntax ok", bool(rev.get("ok")))

    level = classify_update(HERE / "core" / "evolution" / "loop.py", "x = 1")
    dang = classify_update(r"C:\Windows\System32\x.py", "os.remove('a')")
    check("Safe auto-update levels", level in {UpdateLevel.SAFE, UpdateLevel.CAUTION} and dang == UpdateLevel.DANGEROUS)
    check("DANGEROUS blocked", may_auto_apply(UpdateLevel.DANGEROUS, False) is False)

    from core.evolution.boot import boot_all
    boot = boot_all(resume_evolution=False)
    check("Boot all systems", bool(boot.get("ok")) and boot.get("active_count", 0) >= 20, f"{boot.get('active_count')}/{boot.get('total_count')}")

    from ui.app_server import UiApp, WEB_DIR
    check("UI web assets", (WEB_DIR / "index.html").exists() and (WEB_DIR / "styles.css").exists())
    ui = UiApp()
    st = ui.status()
    check("UI status payload", st.get("brand") == "REIS AI")

    from core.telegram_bot import TelegramBot
    bot = TelegramBot(token="", handler=lambda t, m: "ok")
    check("Telegram unconfigured", bot.configured is False)
    bot2 = TelegramBot(token="123456:ABC-DEF", handler=lambda t, m: f"R:{t}")
    bot2.send_message = lambda *a, **k: {"ok": True}  # type: ignore
    check("Telegram configured shape", bot2.configured is True)
    out = bot2.handle_update({
        "message": {"chat": {"id": 1}, "from": {"id": 1}, "text": "/start"}
    })
    check("Telegram /start local", out.get("ok") is True and out.get("kind") == "start")
    out2 = bot2.handle_update({
        "message": {"chat": {"id": 1}, "from": {"id": 1}, "text": "selam"}
    })
    check("Telegram message local", out2.get("ok") is True)

    km = KnowledgeMemory()
    kid = km.remember("demo problem", "demo solution", source="test", success=True)
    hits = km.lookup("demo problem")
    check("Knowledge memory", kid > 0 and any("demo" in str(h.get("problem") or h.get("content") or "") for h in hits))

    pmap = ProjectMapper().build()
    check("Project mapper", pmap.get("file_count", 0) > 10)

    st = EvolutionState(HERE / "memory" / "_evo_state_test.json")
    st.start("unit", ["a", "b"])
    st.mark("a", {"ok": True})
    un = st.unfinished()
    check("Task state resume", un is not None and un.get("current") == "b")
    st.mark("b", {"ok": True})
    check("Task state complete", st.load().get("status") == "COMPLETED")

    # feature builder + live evolution (creates desktop organizer if missing)
    feat = SelfFeatureBuilder().build("Desktop organization tool missing.")
    check(
        "Feature builder desktop",
        bool(feat.get("ok")) or feat.get("stage") in {"evolver", "review", "policy"} or (HERE / "tools" / "desktop_organizer.py").exists(),
        str(feat.get("reason") or feat.get("stage") or feat.get("ok")),
    )

    loop = EvolutionLoop()
    evo = loop.run("Kendini analiz et, eksiklerini bul ve geliştir.", resume=False)
    check("Evolution loop run", bool(evo.get("ok")), (evo.get("message") or "")[:200])
    check("Evolution analyzed own code", bool((evo.get("data") or {}).get("diagnostics")))

    if (HERE / "tools" / "desktop_organizer.py").exists():
        from tools.desktop_organizer import organize
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "a.txt").write_text("x", encoding="utf-8")
            r = organize(p, dry_run=True)
            check("Desktop organizer dry_run", bool(r.get("ok")) and r.get("count") == 1)
    else:
        check("Desktop organizer dry_run", False, "module missing")

    sandbox.unlink(missing_ok=True)
    heal_file.unlink(missing_ok=True)
    (HERE / "memory" / "_evo_state_test.json").unlink(missing_ok=True)


def main() -> int:
    print(f"{Fore.CYAN}{'=' * 70}\n  REIS AI — SELF EVOLUTION V2  ({datetime.now():%H:%M:%S})\n{'=' * 70}{Style.RESET_ALL}\n")
    run()
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = total - passed
    report = {
        "tarih": datetime.now().isoformat(timespec="seconds"),
        "toplam": total,
        "gecen": passed,
        "basarisiz": failed,
        "detaylar": [{"test": n, "gecti": o, "detay": d} for n, o, d in RESULTS],
    }
    out = HERE / "logs" / "SELF_EVOLUTION_TEST.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  SONUÇ: {passed}/{total}")
    print(f"  Rapor: {out}")
    if failed:
        print(f"  {Fore.RED}BAŞARISIZ{Style.RESET_ALL}")
    else:
        print(f"  {Fore.GREEN}SELF-EVOLUTION HAZIR{Style.RESET_ALL}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
