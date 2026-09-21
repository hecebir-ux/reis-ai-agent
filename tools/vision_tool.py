from __future__ import annotations

import base64
from pathlib import Path

import requests

import config
from core.llm_client import OllamaClient
from core.model_router.router import ModelRouter


class VisionTool:
    def __init__(self, llm: OllamaClient | None = None):
        self.llm = llm or OllamaClient()
        self.router = ModelRouter(self.llm)

    def analyze_image(self, path: str, prompt: str = "Bu görseli Türkçe kısaca açıkla.") -> dict:
        info = self.router.resolve("VISION")
        model = info.get("model")
        if not model:
            return {"success": False, "error": "Vision modeli yok. Mevcut modellerle devam."}
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": "Görsel bulunamadı"}
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        try:
            r = self.llm.session.post(
                f"{self.llm.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [b64],
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 250},
                },
                timeout=min(self.llm.timeout, 120),
            )
            r.raise_for_status()
            return {"success": True, "model": model, "text": r.json().get("response", "")}
        except Exception as e:
            return {"success": False, "error": str(e), "model": model}

    def ocr_stub(self, path: str) -> dict:
        r = self.analyze_image(path, "Görseldeki tüm metni olduğu gibi çıkar. Sadece metin yaz.")
        return r
