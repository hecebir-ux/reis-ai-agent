#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REIS AI MAX — birim + self-debug + regression sarmalayıcı."""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.chdir(str(HERE))

from colorama import Fore, Style, init

init()

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    mark = f"{Fore.GREEN}[OK]{Style.RESET_ALL}" if cond else f"{Fore.RED}[HATA]{Style.RESET_ALL}"
    print(f"{mark} {name}")
    if detail:
        print(f"       {detail[:220]}")
    RESULTS.append((name, bool(cond), detail))
    return bool(cond)


def run_max_tests() -> None:
    print(f"{Fore.CYAN}=== REIS AI MAX TESTLERİ ==={Style.RESET_ALL}\n")

    import config
    from api.server import ReisAPI
    from core.cache import TTLCache
    from core.commands import parse_command
    from core.decision import DecisionEngine
    from core.env_check import environment_report
    from core.intent.engine import IntentEngine
    from core.model_router.router import ModelRouter
    from core.scaffold import scaffold_python_app, scaffold_telegram_music_bot
    from core.security import RiskLevel, classify_risk, redact, requires_approval
    from core.task_manager.manager import TaskManager
    from core.tester import Tester
    from core.debugger import Debugger
    from core.memory import Memory
    from database.store import SQLiteStore
    from plugins.loader import PluginManager
    from tools.filesystem import FileSystemTool
    from tools.git_tool import GitTool
    from tools.project_tool import ProjectAnalyzer
    from tools.terminal import TerminalTool

    intent = IntentEngine()
    chat_i = intent.classify("selam reis nasılsın")
    code_i = intent.classify("Kendime basit bir Python uygulaması yap")
    check("Intent sohbet", chat_i.primary in {"CHAT", "QUESTION"}, chat_i.primary)
    check("Intent kodlama", "CODING" in code_i.intents or code_i.primary == "CODING", str(code_i.intents))

    risk = classify_risk("git push", "origin main")
    check("Push CRITICAL/HIGH", risk in {RiskLevel.CRITICAL, RiskLevel.HIGH}, risk.value)
    check("Onay gerekli (safe mode)", requires_approval(risk, True))
    check("Secret redact", "***" in redact("api_key=abcd123") or "api_key=***" in redact("api_key=abcd123"))

    cache = TTLCache(ttl_seconds=30)
    cache.set("a", 1)
    check("Cache get", cache.get("a") == 1)

    store = SQLiteStore(HERE / "database" / "reis_max_test.db")
    store.add_memory("ERROR", "ZeroDivisionError demo", key="zdiv", project="demo")
    hits = store.search_memory("ZeroDivision")
    check("SQLite memory arama", any("ZeroDivision" in h["content"] for h in hits))
    tm = TaskManager(store)
    task = tm.create("demo task")
    tm.set_status(task["id"], "RUNNING", step="plan", progress=0.2)
    tm.control(task["id"], "PAUSE")
    paused = store.get_task(task["id"])
    check("Task pause", paused and paused["status"] == "PAUSED", str(paused and paused["status"]))
    recovered = tm.recover_unfinished()
    check("Recovery unfinished", any(t["id"] == task["id"] for t in recovered))

    cmd = parse_command("/models")
    check("Slash /models", cmd == ("/models", ""))

    git = GitTool()
    push = git.push(approved=False)
    check("Git push izinsiz engelli", push.get("needs_approval") or not push.get("success"))

    env = environment_report()
    check("Env raporu python", env["tools"]["python"]["ok"])
    check("Env raporu ollama alanı", "ollama" in env["tools"])

    api = ReisAPI()
    code, body = api.handle("/tools", {})
    check("API /tools", code == 200 and "terminal" in body.get("tools", []))
    code, body = api.handle("/task", {"title": "api-demo"})
    check("API /task", code == 200 and "task" in body)

    plugins = PluginManager().discover()
    check("Telegram plugin keşif", any(p.get("name") == "telegram" for p in plugins))
    load = PluginManager().load("telegram")
    check("Kapalı plugin yüklenmez", not load.get("success"))

    fs = FileSystemTool()
    tdir = Path(config.WORKSPACE_DIR) / "__max_fs__"
    tdir.mkdir(parents=True, exist_ok=True)
    a = tdir / "a.txt"
    fs.write_file(str(a), "alpha")
    fs.copy_path(str(a), str(tdir / "b.txt"))
    cmp = fs.compare_files(str(a), str(tdir / "b.txt"))
    check("FS copy+compare", cmp.get("same") is True)
    shutil.rmtree(tdir, ignore_errors=True)

    term = TerminalTool()
    r = term.run('python -c "print(1)"')
    check("Terminal duration alanı", "duration" in r and r.get("success"))

    # --- Section 58 self-debug ---
    print(f"\n{Fore.CYAN}=== ZORUNLU SELF-DEBUG (madde 58) ==={Style.RESET_ALL}")
    proj = Path(config.WORKSPACE_DIR) / "reis_max_selfdebug"
    if proj.exists():
        shutil.rmtree(proj, ignore_errors=True)
    fs.create_project_dir("reis_max_selfdebug")
    sc = scaffold_python_app(str(proj), title="Self Debug Demo")
    check("1-4 Workspace+python+dosya+test scaffold", sc.get("success") and (proj / "test.py").exists())

    tester = Tester()
    run1 = tester.detect_and_run(str(proj))
    check("5-6 Çalıştır ve test geçti", run1.get("success"), str(run1.get("stdout", ""))[:80])

    (proj / "test.py").unlink(missing_ok=True)
    (proj / "app.py").write_text(
        "def add(a, b):\n    return a / b\n\ndef main():\n    print(add(1, 0))\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    real_bad = tester.detect_and_run(str(proj))
    blob = (real_bad.get("stderr") or "") + (real_bad.get("stdout") or "")
    check("7-8 Kasıtlı hata tespit", (not real_bad.get("success")) and "ZeroDivisionError" in blob, blob[:160])

    mem = Memory()
    sid = mem.start_session("self-debug-max")

    class SilentLLM:
        def generate(self, *a, **k):
            return ""

    dbg = Debugger(SilentLLM())
    fix = dbg.auto_fix(sid, mem, str(proj), real_bad, max_attempts=3)
    check("9-10 Self-debug fix", bool(fix.get("fixed")), str(fix)[:180])
    run_ok = tester.detect_and_run(str(proj))
    check("11-13 Tekrar çalıştır + test", bool(run_ok.get("success")), (run_ok.get("stdout") or "")[:80])

    tg = Path(config.WORKSPACE_DIR) / "telegram-muzik-botu"
    if tg.exists():
        shutil.rmtree(tg, ignore_errors=True)
    fs.create_project_dir("telegram-muzik-botu")
    bot = scaffold_telegram_music_bot(str(tg))
    check("Telegram bot scaffold", bot.get("success") and "TELEGRAM_BOT_TOKEN" in (tg / "bot.py").read_text(encoding="utf-8"))
    bot_test = tester.detect_and_run(str(tg))
    check("Telegram bot test.py", bot_test.get("success") and "TESTS_OK" in (bot_test.get("stdout") or ""), bot_test.get("stdout", "")[:80])

    analyzer = ProjectAnalyzer()
    an = analyzer.analyze(str(proj))
    check("Project analyzer", an.get("success") and an.get("framework") in {"python", "unknown", "flask"})

    dec = DecisionEngine().decide("Bu projeyi production'a deploy et", intent.classify("Bu projeyi production'a deploy et"))
    check("Deploy onay ister", dec.get("needs_approval") is True, str(dec))

    router = ModelRouter()
    resolved = router.resolve("CODING")
    check("Model router coding", resolved.get("model") is not None, str(resolved.get("model")))
    chat_m = router.resolve("CHAT").get("model") or ""
    check("Chat modeli vision değil", "vision" not in chat_m.lower(), chat_m)
    check("Chat ailesi llama3.2", chat_m.lower().split(":")[0] == "llama3.2", chat_m)

    try:
        (HERE / "database" / "reis_max_test.db").unlink(missing_ok=True)
    except Exception:
        pass


def main() -> int:
    print(f"{Fore.CYAN}{'=' * 70}\n  REIS AI MAX — TEST SÜİTİ  ({datetime.now():%H:%M:%S})\n{'=' * 70}{Style.RESET_ALL}\n")
    run_max_tests()
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = total - passed
    ready = failed == 0
    print(f"\n  SONUÇ: {passed}/{total}")
    report = {
        "tarih": datetime.now().isoformat(timespec="seconds"),
        "toplam": total,
        "gecen": passed,
        "basarisiz": failed,
        "reis_ai_ready": ready,
        "detaylar": [{"test": n, "gecti": o, "detay": d} for n, o, d in RESULTS],
    }
    out = HERE / "logs" / "REIS_MAX_TEST_SONUC.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Rapor: {out}")
    if ready:
        print(f"\n  {Fore.GREEN}REIS AI READY{Style.RESET_ALL}\n")
    else:
        print(f"\n  {Fore.RED}REIS AI READY DENMEDİ — başarısız test var{Style.RESET_ALL}\n")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
