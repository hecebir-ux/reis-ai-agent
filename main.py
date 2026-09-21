#!/usr/bin/env python3
"""REIS AI MAX giriş noktası."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(str(BASE_DIR))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from colorama import Fore, Style, init

init()

import config
from core.agent.loop import ReisMaxAgent
from core.commands import COMMANDS, parse_command
from core.env_check import environment_report, format_env_report
from core.llm_client import OllamaClient
from core.logutil import log_system
from core.metrics import metrics
from core.model_router.router import ModelRouter
from plugins.loader import PluginManager


LOGO = f"""{Fore.CYAN}
  REIS AI MAX
{Style.RESET_ALL}  {Fore.GREEN}Local Autonomous Operating Environment{Style.RESET_ALL}
"""


def print_help():
    print(f"\n{Fore.CYAN}Komutlar{Style.RESET_ALL}")
    for k, v in COMMANDS.items():
        print(f"  {Fore.YELLOW}{k:<12}{Style.RESET_ALL} {v}")
    print(f"  {Fore.WHITE}doğal dil{Style.RESET_ALL}   sohbet / proje / analiz\n")


def handle_slash(agent: ReisMaxAgent, name: str, arg: str) -> bool:
    if name in {"/help", "/?"}:
        print_help()
        return True
    if name == "/models":
        h = agent.llm.health_check()
        for m in h.get("models", []):
            print(f"  {m}")
        return True
    if name == "/status":
        h = agent.llm.health_check()
        snap = metrics.snapshot()
        print(f"  Ollama: {'OK' if h.get('ok') else 'HATA'} | sohbet={agent.llm.chat_model} | kod={agent.llm.model}")
        print(f"  CPU/RAM: {snap.get('cpu')} / {snap.get('ram')} | görevler: {len(agent.store.list_tasks())}")
        print(f"  Startup: {snap.get('startup_s')}s | ollama_avg={snap.get('avg_ollama_s')}s | err_rate={snap.get('error_rate')}")
        evo = getattr(agent, "evolution", None)
        if evo:
            print(f"  Evolution: AKTİF | state={evo.state.load().get('status') or 'idle'}")
        return True
    if name == "/boot":
        from core.evolution.boot import boot_all, format_boot_report
        print(format_boot_report(boot_all(llm=agent.llm, agent=agent)))
        return True
    if name == "/env":
        print(format_env_report(environment_report(agent.llm)))
        return True
    if name == "/projects":
        rows = agent.store.list_projects()
        if not rows:
            print("  Kayıtlı proje yok.")
        for p in rows[:20]:
            print(f"  {p.get('name')}  {p.get('path')}")
        return True
    if name == "/tasks":
        rows = agent.store.list_tasks()
        if not rows:
            print("  Görev yok.")
        for t in rows[:20]:
            print(f"  [{t.get('status')}] {t.get('id')} {t.get('title')}")
        return True
    if name == "/memory":
        q = arg or "proje"
        hits = agent.store.search_memory(q)
        if not hits:
            print("  Eşleşme yok.")
        for h in hits:
            print(f"  [{h.get('kind')}] {h.get('content')[:120]}")
        return True
    if name == "/settings":
        print(f"  SAFE_MODE={config.SAFE_MODE} WEB={config.WEB_ENABLED} VISION={config.VISION_ENABLED} VOICE={config.VOICE_ENABLED} BROWSER={config.BROWSER_ENABLED}")
        print(f"  MAX_PARALLEL={config.MAX_PARALLEL_TASKS} TIMEOUT={config.COMMAND_TIMEOUT}")
        return True
    if name == "/tools":
        print("  terminal filesystem python git web vision browser computer document project")
        return True
    if name == "/logs":
        logf = config.LOGS_DIR / "user.log"
        if logf.exists():
            lines = logf.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
            print("\n".join(lines) or "  boş")
        else:
            print("  log yok")
        return True
    if name in {"/stop", "/pause", "/resume", "/retry"}:
        tid = agent.last_task_id
        if not tid:
            print("  Aktif görev yok.")
            return True
        if name == "/stop":
            agent.stop_requested = True
            agent.tasks.control(tid, "STOP")
            print("  Durduruldu.")
        elif name == "/pause":
            agent.paused = True
            agent.tasks.control(tid, "PAUSE")
            print("  Duraklatıldı.")
        elif name == "/resume":
            agent.stop_requested = False
            agent.paused = False
            agent.tasks.control(tid, "RESUME")
            print("  Devam.")
        elif name == "/retry" and agent.context.active_project:
            print("  Son proje yeniden test ediliyor...")
            out = agent._debug_project(agent.context.active_project, "retry")
            print(out.get("message"))
        return True
    if name == "/reset":
        agent.context.messages.clear()
        print("  Bağlam sıfırlandı.")
        return True
    if name == "/evolve":
        out = agent.evolution.run(arg or "Kendini analiz et, eksiklerini bul ve geliştir.", resume=True)
        print(out.get("message") or "")
        return True
    if name == "/diagnose":
        from core.evolution.self_diagnostics import SelfDiagnostics
        d = SelfDiagnostics().scan()
        print(f"  sorun={len(d.get('problems') or [])} eksik={d.get('missing_capabilities')} test_gap={len(d.get('test_gaps') or [])}")
        for rec in d.get("recommendations") or []:
            print(f"  - {rec}")
        return True
    print(f"  Bilinmeyen komut: {name}")
    return True


def startup() -> OllamaClient | None:
    print(LOGO)
    print(f"  Sohbet: {config.OLLAMA_CHAT_MODEL} | Kod: {config.OLLAMA_CODE_MODEL} | Vision: {config.OLLAMA_VISION_MODEL}")
    print(f"  Workspace: {config.WORKSPACE_DIR}")
    print("-" * 64)
    llm = OllamaClient()
    print("[1] Ollama API...")
    h = llm.health_check()
    if not h.get("ok"):
        print(f"  HATA: {h.get('error')}")
        return None
    print(f"  OK — {len(h.get('models', []))} model: {', '.join(h.get('models', []))}")
    router = ModelRouter(llm)
    for role in ("CHAT", "CODING", "VISION"):
        info = router.resolve(role)
        fb = " (fallback)" if info.get("fallback") else ""
        print(f"  {role}: {info.get('model') or 'yok'}{fb}")
    print("[2] Hızlı model testi...")
    router.apply("FAST")
    resp = llm.generate("Türkçe tek cümle: REIS AI MAX hazır.", temperature=0.1, max_tokens=40, label="MAX test", use_code_model=False)
    if "LLM_HATA" in (resp or ""):
        print(f"  Uyarı: {resp[:120]}")
    else:
        print(f"  {resp.strip()[:200]}")
    plugins = PluginManager().discover()
    print(f"[3] Plugin: {len(plugins)} keşfedildi")
    return llm


def interactive(llm: OllamaClient):
    import time

    t0 = time.perf_counter()
    agent = ReisMaxAgent(llm)
    metrics.record_startup(0)  # placeholder until boot finishes

    # Activate ALL self-evolution systems on start
    boot_status = None
    if getattr(config, "EVOLUTION_BOOT", True):
        from core.evolution.boot import boot_all, format_boot_report

        print(f"\n{Fore.CYAN}[4] Self-Evolution sistemleri aktifleştiriliyor...{Style.RESET_ALL}")
        boot_status = boot_all(
            llm=llm,
            agent=agent,
            resume_evolution=getattr(config, "EVOLUTION_BOOT_RESUME", True),
        )
        print(format_boot_report(boot_status))
        metrics.record_startup(time.perf_counter() - t0)

    unfinished = agent.tasks.recover_unfinished()
    if unfinished:
        print(f"  Kurtarma: {len(unfinished)} yarım görev bulundu.")
    evo_unfinished = agent.evolution.state.unfinished()
    if evo_unfinished:
        print(f"  Evolution kaldığı yer: {evo_unfinished.get('current')} / {evo_unfinished.get('goal')}")
    n = (boot_status or {}).get("active_count")
    total = (boot_status or {}).get("total_count")
    if n is not None:
        print(f"\n{Fore.GREEN}Hazır — Self-Evolution {n}/{total} aktif.{Style.RESET_ALL}  /help  |  /evolve  |  quit\n")
    else:
        print(f"\n{Fore.GREEN}Hazır.{Style.RESET_ALL} /help  |  quit\n")
    while True:
        try:
            raw = input(f"{Fore.MAGENTA}REIS MAX >{Style.RESET_ALL} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGüle güle.")
            break
        if not raw:
            continue
        if raw.lower() in {"quit", "exit", "q", "çıkış", "cikis"}:
            print("Güle güle.")
            break
        cmd = parse_command(raw)
        if cmd:
            handle_slash(agent, cmd[0], cmd[1])
            continue
        print()
        result = agent.handle(raw)
        kind = result.get("kind")
        if kind == "chat" and result.get("streamed"):
            print()
        else:
            print(result.get("message") or "")
        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="REIS AI MAX")
    parser.add_argument("--ui", action="store_true", help="Web arayüzünü aç")
    parser.add_argument("--cli", action="store_true", help="Sadece terminal")
    parser.add_argument("--no-browser", action="store_true", help="Tarayıcıyı otomatik açma")
    args, _unknown = parser.parse_known_args()

    try:
        llm = startup()
    except Exception as e:
        print(f"Kurulum hatası: {type(e).__name__}: {e}")
        llm = None
    if llm is None:
        print("Ollama hazır değil. Yine de sınırlı mod.")
        llm = OllamaClient()
    log_system("REIS AI MAX started")

    use_ui = args.ui or (getattr(config, "UI_ENABLED", True) and not args.cli)
    if use_ui:
        from ui.app_server import run_ui

        print(f"\n{Fore.CYAN}Web arayüzü açılıyor...{Style.RESET_ALL}")
        run_ui(
            host=getattr(config, "UI_HOST", "127.0.0.1"),
            port=getattr(config, "UI_PORT", 8765),
            open_browser=getattr(config, "UI_OPEN_BROWSER", True) and not args.no_browser,
            llm=llm,
        )
        return

    interactive(llm)


if __name__ == "__main__":
    main()
