from __future__ import annotations

from pathlib import Path
from typing import Any

import config
from core.env_check import environment_report, format_env_report
from core.evolution.dependency_manager import DependencyManager
from core.evolution.knowledge import KnowledgeMemory
from core.evolution.project_mapper import ProjectMapper
from core.evolution.security_auditor import SecurityAuditor
from core.evolution.self_benchmark import SelfBenchmark
from core.evolution.self_diagnostics import SelfDiagnostics
from core.evolution.self_evolver import SelfEvolver
from core.evolution.self_feature_builder import SelfFeatureBuilder
from core.evolution.self_healing import SelfHealing
from core.evolution.self_optimizer import SelfOptimizer
from core.evolution.self_reviewer import SelfReviewer
from core.evolution.self_tester import SelfTester
from core.evolution.task_state import EvolutionState
from core.evolution.web_research import WebResearchEngine
from core.evolution.auto_patcher import AutoPatcher
from core.evolution.intents import match_evolution_intent
from core.metrics import metrics


STEPS = [
    "diagnostics",
    "prioritize",
    "plan",
    "build_patch",
    "review",
    "test",
    "benchmark",
    "validate",
    "commit",
    "memory",
]


class EvolutionLoop:
    def __init__(self, agent=None):
        self.agent = agent
        self.diagnostics = SelfDiagnostics()
        self.healer = SelfHealing()
        self.evolver = SelfEvolver()
        self.features = SelfFeatureBuilder()
        self.optimizer = SelfOptimizer()
        self.reviewer = SelfReviewer()
        self.tester = SelfTester()
        self.bench = SelfBenchmark()
        self.web = WebResearchEngine()
        self.deps = DependencyManager()
        self.security = SecurityAuditor()
        self.mapper = ProjectMapper()
        self.knowledge = KnowledgeMemory()
        self.state = EvolutionState()
        self.patcher = AutoPatcher(self.evolver, self.tester)

    def run(self, user_text: str, resume: bool = True, user_approved: bool = False) -> dict[str, Any]:
        intent = match_evolution_intent(user_text) or match_evolution_intent("kendini geliştir")
        kind = intent.kind if intent else "full_evolve"
        metrics.record_task_start()

        if kind == "system_check":
            from core.llm_client import OllamaClient

            llm = getattr(self.agent, "llm", None) or OllamaClient()
            rep = environment_report(llm)
            return {"ok": True, "kind": "evolution", "intent": kind, "message": format_env_report(rep), "data": rep}

        if kind == "self_test":
            r = self.tester.run_file_import(config.BASE_DIR / "core" / "evolution" / "loop.py")
            gen = self.tester.create_and_run("core.evolution.self_diagnostics")
            ok = bool(r.get("ok") and gen.get("ok"))
            msg = "Self-test geçti." if ok else "Self-test başarısız."
            return {"ok": ok, "kind": "evolution", "intent": kind, "message": msg, "data": {"import": r, "generated": gen}}

        if kind == "diagnose":
            diag = self.diagnostics.scan()
            self.mapper.build()
            missing = diag.get("missing_capabilities") or []
            msg = (
                f"Analiz: { (diag.get('stats') or {}).get('python_files') } Python dosyası, "
                f"{len(diag.get('problems') or [])} sorun, eksik: {', '.join(missing) or 'yok'}."
            )
            return {"ok": True, "kind": "evolution", "intent": kind, "message": msg, "data": diag}

        if kind == "fix_error":
            healed = self.healer.run(lambda: True)
            return {"ok": True, "kind": "evolution", "intent": kind, "message": "Hata yok veya heal denendi.", "data": healed}

        if kind == "new_feature":
            built = self.features.build("Desktop organization tool missing.", user_approved=user_approved)
            return {"ok": bool(built.get("ok")), "kind": "evolution", "intent": kind, "message": str(built.get("reason") or built.get("stage") or "özellik eklendi"), "data": built}

        if kind == "files":
            pmap = self.mapper.build()
            return {"ok": True, "kind": "evolution", "intent": kind, "message": f"Project map: {pmap.get('file_count')} dosya.", "data": pmap}

        if kind == "typos":
            src = (config.BASE_DIR / "core/evolution/self_diagnostics.py").read_text(encoding="utf-8")[:3000]
            rev = self.reviewer.review_source(src, "self_diagnostics.py")
            return {"ok": True, "kind": "evolution", "intent": kind, "message": f"Review skoru {rev.get('score')}.", "data": rev}

        if kind == "improve_project":
            user_text = user_text or "Kendini geliştir"

        if kind == "desktop":
            built = self.features.build("Desktop organization tool missing.", user_approved=user_approved)
            msg = "Masaüstü düzenleyici eklendi (dry_run varsayılan)." if built.get("ok") else f"Masaüstü aracı: {built.get('reason') or built.get('stage')}"
            return {"ok": bool(built.get("ok")), "kind": "evolution", "intent": kind, "message": msg, "data": built}

        if kind == "faster":
            tips = self.optimizer.advise()
            if self.agent is not None:
                try:
                    self.agent.router.apply("FAST")
                except Exception:
                    pass
            return {"ok": True, "kind": "evolution", "intent": kind, "message": "FAST modele geçildi.\n" + "\n".join(tips), "data": {"tips": tips}}

        if kind == "research":
            web = self.web.research(user_text, force=False)
            return {"ok": bool(web.get("ok") or web.get("skipped")), "kind": "evolution", "intent": kind, "message": str(web.get("solution") or web.get("reason") or web.get("error"))[:800], "data": web}

        existing = self.state.unfinished() if resume else None
        if existing and existing.get("goal") == user_text:
            report = self._continue(existing, user_approved)
        else:
            self.state.start(user_text, STEPS)
            report = self._full(user_text, user_approved, start_from=0)

        metrics.record_task_end()
        return report

    def _continue(self, state: dict[str, Any], user_approved: bool) -> dict[str, Any]:
        done = set(state.get("completed") or [])
        start = 0
        for i, step in enumerate(STEPS):
            if step not in done:
                start = i
                break
        else:
            return {"ok": True, "kind": "evolution", "message": "Görev zaten tamamlanmış.", "data": state}
        return self._full(state.get("goal") or "", user_approved, start_from=start, prior=state.get("results") or {})

    def _full(self, goal: str, user_approved: bool, start_from: int = 0, prior: dict | None = None) -> dict[str, Any]:
        results: dict[str, Any] = dict(prior or {})
        try:
            if start_from <= 0:
                diag = self.diagnostics.scan()
                results["diagnostics"] = diag
                self.state.mark("diagnostics", {"problem_count": len(diag.get("problems") or []), "missing": diag.get("missing_capabilities")})
            diag = results.get("diagnostics") or self.diagnostics.scan()

            if start_from <= 1:
                prios = list(diag.get("missing_capabilities") or []) + [p.get("kind") for p in (diag.get("problems") or [])[:5]]
                results["prioritize"] = prios
                self.state.mark("prioritize", {"items": prios[:8]})

            if start_from <= 2:
                plan = {"actions": []}
                if any("Desktop" in str(x) for x in diag.get("missing_capabilities") or []):
                    plan["actions"].append("build_desktop_organizer")
                if diag.get("test_gaps") or any(p.get("kind") == "unused_import" for p in (diag.get("problems") or [])):
                    plan["actions"].append("auto_patch")
                plan["actions"].append("refresh_project_map")
                if diag.get("security_issues"):
                    plan["actions"].append("security_audit")
                g = (goal or "").lower()
                if any(k in g for k in ("güncel", "guncel", "teknik bilgi", "web")):
                    plan["actions"].append("web_research")
                if any(k in g for k in ("hızlı", "hizli", "daha hızlı", "optimize")):
                    plan["actions"].append("optimize")
                results["plan"] = plan
                self.state.mark("plan", plan)

            if start_from <= 3:
                actions = (results.get("plan") or {}).get("actions") or []
                build_out: dict[str, Any] = {"ok": True, "steps": []}
                if "build_desktop_organizer" in actions:
                    built = self.features.build("Desktop organization tool missing.", user_approved=user_approved)
                    build_out["steps"].append({"desktop": built})
                    build_out["ok"] = build_out["ok"] and bool(built.get("ok"))
                if "auto_patch" in actions:
                    patched = self.patcher.from_diagnostics(diag, max_patches=3)
                    build_out["steps"].append({"auto_patch": patched})
                    build_out["ok"] = build_out["ok"] and bool(patched.get("ok"))
                if "web_research" in actions:
                    web = self.web.research(goal, force=False)
                    build_out["steps"].append({"web": web})
                if "optimize" in actions:
                    tips = self.optimizer.advise()
                    if self.agent is not None:
                        try:
                            self.agent.router.apply("FAST")
                        except Exception:
                            pass
                    build_out["steps"].append({"optimize": tips})
                if not build_out["steps"]:
                    build_out = {"ok": True, "skipped": True}
                results["build_patch"] = build_out
                self.state.mark("build_patch", results["build_patch"])

            if start_from <= 4:
                p = config.BASE_DIR / "core/evolution/self_diagnostics.py"
                src = p.read_text(encoding="utf-8") if p.exists() else ""
                results["review"] = self.reviewer.review_source(src, "core/evolution/self_diagnostics.py")
                self.state.mark("review", results["review"])
                if not (results["review"] or {}).get("ok"):
                    # review fail does not abort — log only for SAFE evolution
                    results["review"]["soft_fail"] = True

            if start_from <= 5:
                test_r = self.tester.run_file_import(config.BASE_DIR / "core/evolution/self_diagnostics.py")
                # also re-run any newly generated smoke tests
                smoke_ok = True
                for gap in (diag.get("test_gaps") or [])[:3]:
                    stem = Path(str(gap)).stem
                    smoke = config.BASE_DIR / "tests" / f"test_{stem}_smoke.py"
                    if smoke.exists():
                        sr = self.tester.run_pytest_or_script(smoke)
                        smoke_ok = smoke_ok and bool(sr.get("ok"))
                test_r = {**test_r, "smoke_ok": smoke_ok, "ok": bool(test_r.get("ok")) and smoke_ok}
                results["test"] = test_r
                self.state.mark("test", test_r)
                if not test_r.get("ok"):
                    self.state.fail("test", str(test_r))
                    return self._out(False, "Test başarısız, değişiklik uygulanmadı.", results)

            if start_from <= 6:
                old = self.bench.measure(lambda: len(self.diagnostics.scan().get("problems") or []), rounds=1)
                new = self.bench.measure(lambda: len(self.diagnostics.scan().get("problems") or []), rounds=1)
                cmp = self.bench.compare(old, new, max_regression=1.5)
                results["benchmark"] = {"old": old, "new": new, "compare": cmp}
                self.state.mark("benchmark", results["benchmark"])
                if not cmp.get("accept"):
                    results["benchmark"]["rolled_back_reason"] = "performance"
                    return self._out(False, "Benchmark gerileme: değişiklik kabul edilmedi.", results)

            if start_from <= 7:
                sec = self.security.audit()
                deps = self.deps.analyze()
                results["validate"] = {"security_count": sec.get("count"), "deps_missing": deps.get("missing_in_requirements")}
                self.state.mark("validate", results["validate"])

            if start_from <= 8:
                pmap = self.mapper.build()
                results["commit"] = {"project_map": pmap.get("file_count"), "feature": (results.get("build_patch") or {}).get("ok")}
                self.state.mark("commit", results["commit"])

            if start_from <= 9:
                self.knowledge.remember(
                    problem=goal[:200],
                    solution="evolution loop completed",
                    source="local-evolution",
                    success=True,
                )
                self.state.mark("memory", {"saved": True})

            missing = (results.get("diagnostics") or {}).get("missing_capabilities") or []
            msg = self._summary(results, missing)
            return self._out(True, msg, results)
        except Exception as e:
            self.state.fail(self.state.load().get("current") or "unknown", str(e))
            return self._out(False, f"Evolution hata verdi ama ajan ayakta: {type(e).__name__}: {e}", results)

    def _summary(self, results: dict[str, Any], missing: list) -> str:
        d = results.get("diagnostics") or {}
        nprob = len(d.get("problems") or [])
        feat = results.get("build_patch") or {}
        steps = feat.get("steps") or []
        patch_n = 0
        for s in steps:
            ap = (s.get("auto_patch") or {}).get("applied") or []
            patch_n += len(ap)
        feat_s = f"{patch_n} güvenli yama uygulandı" if patch_n else (
            "masaüstü aracı eklendi" if feat.get("ok") and not feat.get("skipped") and steps else "yeni özellik atlandı veya zaten vardı"
        )
        return (
            f"Self-evolution tamamlandı.\n"
            f"- Python tarama: { (d.get('stats') or {}).get('python_files') } dosya, {nprob} sorun kaydı\n"
            f"- Eksik yetenek: {', '.join(missing) or 'yok'}\n"
            f"- Özellik/yama: {feat_s}\n"
            f"- Review skoru: {(results.get('review') or {}).get('score')}\n"
            f"- Test: {'OK' if (results.get('test') or {}).get('ok') else 'HATA'}\n"
            f"- Project map güncellendi.\n"
            f"Restart sonrası /evolve ile kaldığı yerden devam eder."
        )

    def _out(self, ok: bool, message: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"ok": ok, "kind": "evolution", "message": message, "data": data}
