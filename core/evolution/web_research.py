from __future__ import annotations

from typing import Any

import config
from core.evolution.knowledge import KnowledgeMemory
from tools.web_tool import WebTool

DOC_URLS = [
    ("python", "https://docs.python.org/3/"),
    ("ollama", "https://github.com/ollama/ollama"),
    ("pip", "https://pip.pypa.io/en/stable/"),
    ("requests", "https://requests.readthedocs.io/en/latest/"),
    ("flask", "https://flask.palletsprojects.com/en/stable/"),
    ("fastapi", "https://fastapi.tiangolo.com/"),
]


class WebResearchEngine:
    def __init__(self, web: WebTool | None = None, memory: KnowledgeMemory | None = None):
        self.web = web or WebTool()
        self.memory = memory or KnowledgeMemory()

    def needed(self, query: str, local_hits: list | None = None) -> bool:
        q = (query or "").lower()
        if local_hits:
            return False
        keys = ("güncel", "guncel", "api", "docs", "ollama", "changelog", "version", "hata mesaj", "github")
        return any(k in q for k in keys)

    def research(self, query: str, force: bool = False) -> dict[str, Any]:
        mem = self.memory.lookup(query)
        if mem and not force:
            return {
                "ok": True,
                "from_memory": True,
                "sources": [m.get("source") for m in mem],
                "solution": mem[0].get("solution") or mem[0].get("content"),
            }
        if not force and not self.needed(query, None):
            return {"ok": True, "skipped": True, "reason": "local-first: web gerekmedi"}
        if not config.WEB_ENABLED:
            return {"ok": False, "degraded": True, "error": "WEB_ENABLED=false"}

        sources: list[dict[str, Any]] = []
        try:
            url = self._pick_url(query)
            page = self.web.fetch_readable(url, max_chars=2000)
            if page.get("success"):
                text = page.get("readable_text") or ""
                sources.append({"url": url, "ok": True, "excerpt": text[:900]})
                solution = text[:900]
                self.memory.remember(query, solution, source=url, success=True)
                return {
                    "ok": True,
                    "from_memory": False,
                    "sources": sources,
                    "solution": solution,
                    "url": url,
                }
            sources.append({"url": url, "ok": False, "error": page.get("error")})
        except Exception as e:
            return {"ok": False, "degraded": True, "error": str(e), "sources": sources}
        return {"ok": False, "degraded": True, "error": "web fetch failed", "sources": sources}

    def _pick_url(self, query: str) -> str:
        q = query.lower()
        for key, url in DOC_URLS:
            if key in q:
                return url
        return "https://docs.python.org/3/"
