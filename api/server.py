from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import config
from core.env_check import environment_report
from core.llm_client import OllamaClient
from core.model_router.router import ModelRouter
from core.task_manager.manager import TaskManager
from database.store import SQLiteStore
from plugins.loader import PluginManager


class ReisAPI:
    def __init__(self):
        self.llm = OllamaClient()
        self.router = ModelRouter(self.llm)
        self.store = SQLiteStore()
        self.tasks = TaskManager(self.store)
        self.plugins = PluginManager()

    def handle(self, path: str, payload: dict) -> tuple[int, dict[str, Any]]:
        if path == "/models":
            return 200, {"models": self.router.available_models(force=True), "roles": self.router.roles}
        if path == "/status":
            return 200, environment_report(self.llm)
        if path == "/projects":
            return 200, {"projects": self.store.list_projects()}
        if path == "/tasks":
            return 200, {"tasks": self.store.list_tasks()}
        if path == "/tools":
            return 200, {"tools": ["terminal", "filesystem", "python", "git", "web", "vision", "browser", "computer"]}
        if path == "/plugins":
            return 200, {"plugins": self.plugins.list_all()}
        if path == "/chat":
            msg = payload.get("message") or payload.get("prompt") or ""
            if not msg:
                return 400, {"error": "message gerekli"}
            self.router.apply("CHAT")
            text = self.llm.chat([{"role": "user", "content": msg}], max_tokens=400)
            return 200, {"reply": text}
        if path == "/task":
            title = payload.get("title") or payload.get("goal") or ""
            if not title:
                return 400, {"error": "title gerekli"}
            task = self.tasks.create(title, payload.get("description", ""))
            return 200, {"task": task}
        return 404, {"error": "bilinmeyen endpoint"}


def make_handler(api: ReisAPI):
    class Handler(BaseHTTPRequestHandler):
        def _auth_ok(self) -> bool:
            token = getattr(config, "API_TOKEN", "") or ""
            if not token:
                return True
            given = self.headers.get("Authorization", "")
            return given == f"Bearer {token}" or self.headers.get("X-API-Token") == token

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._auth_ok():
                self._send(401, {"error": "unauthorized"})
                return
            path = urlparse(self.path).path
            code, body = api.handle(path, {})
            self._send(code, body)

        def do_POST(self):
            if not self._auth_ok():
                self._send(401, {"error": "unauthorized"})
                return
            path = urlparse(self.path).path
            code, body = api.handle(path, self._read_json())
            self._send(code, body)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def serve_forever(host: str | None = None, port: int | None = None) -> None:
    api = ReisAPI()
    server = ThreadingHTTPServer((host or config.API_HOST, port or config.API_PORT), make_handler(api))
    server.serve_forever()
