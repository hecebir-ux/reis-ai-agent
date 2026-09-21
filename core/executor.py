from pathlib import Path
import config
from core.llm_client import OllamaClient
from core.planner import Planner
from core.coder import Coder
from core.tester import Tester
from core.debugger import Debugger
from core.memory import Memory
from tools.terminal import TerminalTool
from tools.filesystem import FileSystemTool
from tools.python_tool import PythonTool
from tools.web_tool import WebTool


class Executor:
    def __init__(self, llm: OllamaClient):
        self.llm = llm
        self.planner = Planner(llm)
        self.fs = FileSystemTool()
        self.terminal = TerminalTool()
        self.python = PythonTool()
        self.web = WebTool()
        self.coder = Coder(llm, self.fs, self.python)
        self.tester = Tester()
        self.debugger = Debugger(llm)
        self.max_iterations = config.MAX_ITERATIONS

    def run(self, goal: str, memory: Memory) -> dict:
        session_id = memory.start_session(goal)
        memory.add_step(session_id, "plan", f"Hedef inceleniyor: '{goal}'")

        plan = self.planner.build_plan(goal)
        memory.set_plan(session_id, plan)
        proje_adi = plan.get("proje_adi") or "proje"
        memory.add_step(session_id, "plan", f"Plan hazirlandi: {proje_adi} ({len(plan.get('ana_adimlar', []))} adim)", plan)
        project_dir_r = self.fs.create_project_dir(proje_adi)
        if not project_dir_r["success"]:
            memory.finish(session_id, "failed", f"Proje klasoru olusturulamadi: {project_dir_r.get('error')}")
            return {"ok": False, "error": project_dir_r.get("error"), "session_id": session_id}
        project_dir = project_dir_r["path"]

        bagimliliklar = plan.get("bagimliliklar", [])
        if bagimliliklar:
            req_r = self.python.create_requirements(project_dir, bagimliliklar)
            if req_r.get("success"):
                inst_r = self.python.install_requirements(str(Path(project_dir) / "requirements.txt"))
                memory.add_step(session_id, "setup", "Bagimliliklar kuruldu", inst_r)

        adimlar = plan.get("ana_adimlar", [])
        total_context_parts = []
        last_test_result = None

        for idx, adim in enumerate(adimlar, start=1):
            if idx > self.max_iterations:
                memory.add_error(session_id, "loop", f"Maksimum iterasyon ({self.max_iterations}) asildi")
                break

            memory.add_step(session_id, "execute", f"Adim {idx}/{len(adimlar)}: {adim.get('adim')}", adim)
            step_ctx = "\n".join(total_context_parts[-8:])

            code_results = self.coder.code_from_plan(adim, project_dir, context=step_ctx)
            memory.add_step(session_id, "code", f"Kod yazildi: {len(code_results)} dosya", code_results)

            for cr in code_results:
                res = cr.get("result", {})
                if res.get("success"):
                    total_context_parts.append(f"{cr['file']} yazildi ({res.get('bytes', 0)} byte)")
                else:
                    total_context_parts.append(f"{cr['file']} HATA: {res.get('error')}")

            if adim.get("test_gerekli"):
                memory.add_step(session_id, "test", "Test basliyor...")
                test_result = self.tester.detect_and_run(project_dir)
                last_test_result = test_result

                if not test_result.get("success"):
                    memory.add_error(
                        session_id,
                        f"step_{idx}_test",
                        "\n".join(self.tester.extract_errors(test_result))[:1000] or test_result.get("stderr", "")[:1000]
                    )
                    step_ctx_extra = step_ctx + "\n" + f"Hata: {test_result.get('stderr', '')[:500]}"
                    fix_result = self.debugger.auto_fix(
                        session_id, memory, project_dir, test_result, step_context=step_ctx_extra
                    )
                    if fix_result.get("fixed"):
                        memory.add_step(session_id, "debug", "Hata otomatik olarak duzeltildi", fix_result)
                        last_test_result = fix_result.get("last_result", test_result)
                    else:
                        memory.add_step(
                            session_id, "debug",
                            f"Hata duzeltilemedi: {fix_result.get('reason')}",
                            fix_result
                        )
                else:
                    memory.add_step(session_id, "test", "Test BASARILI", test_result)

        final_test = last_test_result or self.tester.detect_and_run(project_dir)
        status = "success" if final_test.get("success") else "partial"
        memory.finish(session_id, status, final_test.get("stderr", "")[:500] or "Tamamlandi")

        return {
            "ok": final_test.get("success"),
            "session_id": session_id,
            "project_dir": project_dir,
            "final_test": final_test,
            "status": status,
            "plan": plan,
        }
