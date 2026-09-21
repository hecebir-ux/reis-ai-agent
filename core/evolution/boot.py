"""Boot all self-evolution subsystems when REIS AI starts."""
from __future__ import annotations

import time
from typing import Any

import config
from core.metrics import metrics
from core.model_router.router import ModelRouter


def boot_all(llm=None, agent=None, resume_evolution: bool = True) -> dict[str, Any]:
    """Activate diagnostics, memory, mapper, router, security, deps, healer, etc."""
    t0 = time.perf_counter()
    status: dict[str, Any] = {"ok": True, "systems": {}, "messages": []}

    def mark(name: str, ok: bool, detail: str = "") -> None:
        status["systems"][name] = {"ok": ok, "detail": detail}
        if not ok:
            status["ok"] = False

    try:
        from core.evolution.self_diagnostics import SelfDiagnostics
        from core.evolution.knowledge import KnowledgeMemory
        from core.evolution.dependency_manager import DependencyManager
        from core.evolution.security_auditor import SecurityAuditor
        from core.evolution.project_mapper import ProjectMapper
        from core.evolution.task_state import EvolutionState
        from core.evolution.safe_auto_update import UpdateLevel
        from core.evolution.loop import EvolutionLoop
        from core.evolution.intents import match_evolution_intent

        mark("self_diagnostics", True)
        mark("self_healing", True)
        mark("self_evolver", True)
        mark("self_feature_builder", True)
        mark("self_optimizer", True)
        mark("self_reviewer", True)
        mark("self_tester", True)
        mark("self_benchmark", True)
        mark("web_research", True)
        mark("knowledge_memory", True)
        mark("dependency_manager", True)
        mark("security_auditor", True)
        mark("project_mapper", True)
        mark("task_state", True)
        mark("safe_auto_update", True)
        mark("auto_patcher", True)
        mark("evolution_loop", True)
        mark("intents", bool(match_evolution_intent("Kendini geliştir")))
    except Exception as e:
        mark("evolution_package", False, str(e))
        status["elapsed_s"] = round(time.perf_counter() - t0, 3)
        return status

    # Model router — bind all roles
    try:
        router = ModelRouter(llm) if llm is not None else ModelRouter()
        roles = {}
        for role in ("FAST", "CODING", "ANALYSIS", "VISION", "REVIEW", "CHAT"):
            info = router.resolve(role)
            roles[role] = info.get("model") or info.get("requested")
        mark("model_router", True, str(roles))
        status["models"] = roles
        if agent is not None and hasattr(agent, "router"):
            agent.router = router
    except Exception as e:
        mark("model_router", False, str(e))

    # Project map
    try:
        pmap = ProjectMapper().build()
        mark("project_map", True, f"{pmap.get('file_count')} files")
        status["project_map_files"] = pmap.get("file_count")
    except Exception as e:
        mark("project_map", False, str(e))

    # Knowledge + SQLite
    try:
        km = KnowledgeMemory()
        km.remember("boot", "evolution systems online", source="boot", success=True)
        mark("sqlite_knowledge", True)
    except Exception as e:
        mark("sqlite_knowledge", False, str(e))

    # Quick diagnostics (lightweight stats)
    try:
        diag = SelfDiagnostics().scan()
        status["diagnostics"] = {
            "python_files": (diag.get("stats") or {}).get("python_files"),
            "problems": len(diag.get("problems") or []),
            "missing": diag.get("missing_capabilities") or [],
            "test_gaps": len(diag.get("test_gaps") or []),
        }
        mark("diagnostics_scan", True, f"{status['diagnostics']['python_files']} py")
    except Exception as e:
        mark("diagnostics_scan", False, str(e))

    # Security + deps snapshot
    try:
        sec = SecurityAuditor().audit()
        mark("security_audit", True, f"{sec.get('count')} findings")
        status["security_count"] = sec.get("count")
    except Exception as e:
        mark("security_audit", False, str(e))

    try:
        deps = DependencyManager().analyze()
        mark("dependency_check", True, f"missing={deps.get('missing_in_requirements')}")
    except Exception as e:
        mark("dependency_check", False, str(e))

    # Desktop tool present?
    try:
        desktop = (config.BASE_DIR / "tools" / "desktop_organizer.py").exists()
        mark("desktop_organizer", desktop, "ready" if desktop else "missing")
    except Exception as e:
        mark("desktop_organizer", False, str(e))

    # Metrics
    elapsed = time.perf_counter() - t0
    metrics.record_startup(elapsed)
    status["elapsed_s"] = round(elapsed, 3)
    status["levels"] = [UpdateLevel.SAFE.value, UpdateLevel.CAUTION.value, UpdateLevel.DANGEROUS.value]

    # Resume unfinished evolution task
    status["resume"] = None
    if resume_evolution:
        try:
            st = EvolutionState()
            unfinished = st.unfinished()
            if unfinished and agent is not None and hasattr(agent, "evolution"):
                status["messages"].append(
                    f"Yarım evolution: {unfinished.get('current')} — /evolve ile devam"
                )
                status["resume"] = unfinished
            mark("task_resume", True, "pending" if unfinished else "clean")
        except Exception as e:
            mark("task_resume", False, str(e))

    # Attach live EvolutionLoop if agent provided
    if agent is not None:
        try:
            if not getattr(agent, "evolution", None):
                agent.evolution = EvolutionLoop(agent)
            mark("agent_evolution", True)
        except Exception as e:
            mark("agent_evolution", False, str(e))

    status["active_count"] = sum(1 for v in status["systems"].values() if v.get("ok"))
    status["total_count"] = len(status["systems"])
    return status


def format_boot_report(status: dict[str, Any]) -> str:
    lines = [
        f"Self-Evolution boot: {status.get('active_count')}/{status.get('total_count')} aktif "
        f"({status.get('elapsed_s')}s)"
    ]
    for name, info in (status.get("systems") or {}).items():
        mark = "OK" if info.get("ok") else "!"
        detail = info.get("detail") or ""
        lines.append(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    diag = status.get("diagnostics") or {}
    if diag:
        lines.append(
            f"  Tarama: {diag.get('python_files')} dosya, "
            f"{diag.get('problems')} sorun, test_gap={diag.get('test_gaps')}"
        )
    models = status.get("models") or {}
    if models:
        lines.append(
            "  Modeller: "
            + ", ".join(f"{k}={v}" for k, v in models.items() if k in {"FAST", "CODING", "ANALYSIS", "VISION"})
        )
    for m in status.get("messages") or []:
        lines.append(f"  {m}")
    return "\n".join(lines)
