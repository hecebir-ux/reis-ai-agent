from __future__ import annotations

import config


class BrowserAgent:
    def __init__(self):
        self.enabled = bool(config.BROWSER_ENABLED)

    def status(self) -> dict:
        playwright = False
        try:
            import playwright  # noqa: F401
            playwright = True
        except Exception:
            playwright = False
        return {
            "success": True,
            "enabled": self.enabled,
            "playwright": playwright,
            "note": "Tarayıcı otomasyonu kapalı veya onaylı oturum gerektirir. Şifre/token rastgele sitelere gönderilmez.",
        }

    def open_url(self, url: str) -> dict:
        if not self.enabled:
            return {"success": False, "error": "BROWSER_ENABLED=false. Config'den açın."}
        return {"success": False, "error": "Playwright kurulu değil; mimari hazır, gerçek otomasyon sonraki aşama.", "url": url}
