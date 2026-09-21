"""Local REIS AI web UI — no IDE required, opens in browser."""
from __future__ import annotations

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import config
from core.agent.loop import ReisMaxAgent
from core.evolution.boot import boot_all, format_boot_report
from core.llm_client import OllamaClient
from core.metrics import metrics
from core.model_router.router import ModelRouter

WEB_DIR = Path(__file__).resolve().parent / "web"
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class UiApp:
    def __init__(self, llm: OllamaClient | None = None):
        self.llm = llm or OllamaClient()
        self.agent = ReisMaxAgent(self.llm)
        self.boot_status: dict[str, Any] = {}
        self._lock = threading.Lock()
        self.router = ModelRouter(self.llm)

    def boot(self) -> dict[str, Any]:
        with self._lock:
            self.boot_status = boot_all(
                llm=self.llm,
                agent=self.agent,
                resume_evolution=getattr(config, "EVOLUTION_BOOT_RESUME", True),
            )
            metrics.record_startup(float(self.boot_status.get("elapsed_s") or 0))
            return self.boot_status

    def handle_message(self, text: str) -> dict[str, Any]:
        raw = (text or "").strip()
        if not raw:
            return {"ok": False, "message": "Boş mesaj", "kind": "error"}
        with self._lock:
            if raw.lower() in {"/boot", "boot"}:
                st = boot_all(llm=self.llm, agent=self.agent)
                self.boot_status = st
                return {"ok": True, "kind": "boot", "message": format_boot_report(st)}
            if raw.lower() in {"/diagnose", "diagnose"}:
                from core.evolution.self_diagnostics import SelfDiagnostics

                d = SelfDiagnostics().scan()
                msg = (
                    f"Tarama: {(d.get('stats') or {}).get('python_files')} dosya, "
                    f"{len(d.get('problems') or [])} sorun.\n"
                    + "\n".join(f"- {r}" for r in (d.get("recommendations") or [])[:6])
                )
                return {"ok": True, "kind": "diagnose", "message": msg, "data": d}
            out = self.agent.handle(raw)
            return {
                "ok": bool(out.get("ok")),
                "kind": out.get("kind") or "chat",
                "message": out.get("message") or "",
                "intent": out.get("intent"),
            }

    def status(self) -> dict[str, Any]:
        h = self.llm.health_check()
        models = {}
        for role in ("FAST", "CODING", "ANALYSIS", "VISION", "CHAT"):
            models[role] = (self.router.resolve(role) or {}).get("model")
        boot = self.boot_status or {}
        return {
            "brand": "REIS AI",
            "ollama_ok": bool(h.get("ok")),
            "models": models,
            "evolution_active": boot.get("active_count") or 0,
            "evolution_total": boot.get("total_count") or 0,
            "startup_s": metrics.snapshot().get("startup_s"),
            "workspace": str(config.WORKSPACE_DIR),
        }


def make_handler(app: UiApp):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(code, data, "application/json; charset=utf-8")

        def _read_json(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self):
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                file = WEB_DIR / "index.html"
                self._send(200, file.read_bytes(), MIME[".html"])
                return
            if path.startswith("/static/"):
                name = path[len("/static/") :]
                file = WEB_DIR / name
                if not file.exists() or not file.is_file():
                    self._json(404, {"error": "not found"})
                    return
                try:
                    file.resolve().relative_to(WEB_DIR.resolve())
                except ValueError:
                    self._json(403, {"error": "forbidden"})
                    return
                self._send(200, file.read_bytes(), MIME.get(file.suffix, "application/octet-stream"))
                return
            if path == "/api/status":
                self._json(200, app.status())
                return
            if path == "/api/boot":
                self._json(200, {"ok": True, "message": format_boot_report(app.boot()), "data": app.boot_status})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            payload = self._read_json()
            if path == "/api/handle":
                msg = payload.get("message") or payload.get("text") or ""
                try:
                    self._json(200, app.handle_message(msg))
                except Exception as e:
                    self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}", "message": str(e)})
                return
            if path == "/api/boot":
                st = app.boot()
                self._json(200, {"ok": True, "message": format_boot_report(st), "data": st})
                return
            self._json(404, {"error": "not found"})

    return Handler


def run_ui(
    host: str | None = None,
    port: int | None = None,
    open_browser: bool = True,
    llm: OllamaClient | None = None,
) -> None:
    host = host or getattr(config, "UI_HOST", "127.0.0.1")
    port = int(port or getattr(config, "UI_PORT", 8765))
    app = UiApp(llm=llm)
    print("[UI] Self-Evolution boot...")
    st = app.boot()
    print(format_boot_report(st))
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    url = f"http://{host}:{port}/"
    print(f"[UI] REIS AI arayüzü: {url}")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[UI] Kapandı.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_ui()
