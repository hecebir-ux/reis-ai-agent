import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote
import config


class WebTool:
    SAFE_DOMAINS = [
        "python.org",
        "docs.python.org",
        "pypi.org",
        "pip.pypa.io",
        "stackoverflow.com",
        "docs.djangoproject.com",
        "flask.palletsprojects.com",
        "fastapi.tiangolo.com",
        "pydantic.dev",
        "requests.readthedocs.io",
        "github.com",
        "docs.github.com",
        "ollama.com",
        "developer.mozilla.org",
        "w3schools.com",
        "devdocs.io",
        "learn.microsoft.com",
        "nodejs.org",
        "docs.npmjs.com",
    ]
    allowed_domains = SAFE_DOMAINS

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "REIS-AI-Agent/1.0 (Research Tool)"
        })

    def _is_safe_domain(self, url: str) -> tuple[bool, str]:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False, f"Gecersiz protokol: {parsed.scheme}"
            host = parsed.hostname or ""
            if not host:
                return False, "Host tanimlanamadi"
            for safe in self.SAFE_DOMAINS:
                if host == safe or host.endswith("." + safe):
                    return True, "OK"
            return False, f"Domain beyaz listede degil: {host}. Sadece resmi dokumantasyon siteleri arastirilabilir."
        except Exception as e:
            return False, f"URL parse hatasi: {e}"

    def fetch(self, url: str) -> dict:
        safe, reason = self._is_safe_domain(url)
        if not safe:
            return {"success": False, "error": reason, "url": url}
        try:
            r = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            r.raise_for_status()
            content_type = r.headers.get("Content-Type", "")
            text = ""
            if "text" in content_type or "json" in content_type or "xml" in content_type:
                text = r.text
            return {
                "success": True,
                "url": url,
                "final_url": r.url,
                "status": r.status_code,
                "content_type": content_type,
                "content": text,
                "length": len(r.content),
            }
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}", "url": url}

    def fetch_readable(self, url: str, max_chars: int = 8000) -> dict:
        r = self.fetch(url)
        if not r["success"]:
            return r
        content = r.get("content", "")
        if not content:
            return {"success": False, "error": "Icerik bos", "url": url}
        try:
            soup = BeautifulSoup(content, "lxml")
        except Exception:
            soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n... [truncated]"
        r["readable_text"] = text
        return r

    def search_web(self, query: str) -> dict:
        try:
            url = "https://docs.python.org/3/search.html?q=" + requests.utils.quote(query)
            page = self.fetch_readable(url, max_chars=1500)
            if page.get("success"):
                return {"success": True, "query": query, "url": url, "excerpt": page.get("readable_text", "")[:800]}
            return {"success": False, "error": page.get("error", "fetch failed"), "degraded": True, "query": query}
        except Exception as e:
            return {"success": False, "error": str(e), "degraded": True, "query": query}
