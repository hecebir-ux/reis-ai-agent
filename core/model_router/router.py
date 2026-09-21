from __future__ import annotations

import config
from core.cache import tool_cache
from core.llm_client import OllamaClient


ROLE_MAP = {
    "CHAT": "chat",
    "FAST": "fast",
    "CODING": "coding",
    "VISION": "vision",
    "RESEARCH": "research",
    "REASONING": "reasoning",
    "ANALYSIS": "analysis",
    "REVIEW": "review",
}


class ModelRouter:
    def __init__(self, llm: OllamaClient | None = None):
        self.llm = llm or OllamaClient()
        self.roles = {
            "chat": config.OLLAMA_CHAT_MODEL,
            "coding": config.OLLAMA_CODE_MODEL,
            "vision": config.OLLAMA_VISION_MODEL,
            "fast": config.OLLAMA_FAST_MODEL,
            "research": config.OLLAMA_RESEARCH_MODEL,
            "reasoning": config.OLLAMA_REASONING_MODEL,
            "analysis": getattr(config, "MODEL_ROUTES", {}).get("ANALYSIS", config.OLLAMA_REASONING_MODEL),
            "review": getattr(config, "MODEL_ROUTES", {}).get("REVIEW", config.OLLAMA_REASONING_MODEL),
        }
        self._available: list[str] | None = None

    def available_models(self, force: bool = False) -> list[str]:
        cache_key = "ollama_models"
        if not force:
            cached = tool_cache.get(cache_key)
            if cached is not None:
                return cached
        h = self.llm.health_check()
        models = h.get("models", []) if h.get("ok") else []
        self._available = models
        tool_cache.set(cache_key, models)
        return models

    def _match(self, wanted: str, models: list[str]) -> str | None:
        if not wanted:
            return None
        w = wanted.lower().strip()
        base = w.split(":")[0]
        exact: list[str] = []
        family: list[str] = []
        for m in models:
            ml = m.lower()
            mbase = ml.split(":")[0]
            if ml == w or ml == f"{base}:latest":
                exact.append(m)
            elif mbase == base:
                family.append(m)
        if exact:
            return exact[0]
        if family:
            return family[0]
        return None

    def resolve(self, role: str) -> dict:
        role_key = ROLE_MAP.get(role.upper(), role.lower())
        wanted = self.roles.get(role_key, self.roles["chat"])
        models = self.available_models()
        chosen = self._match(wanted, models)
        fallback_used = False
        if not chosen:
            fallback_used = True
            for candidate in (
                self.roles["fast"],
                self.roles["chat"],
                self.roles["coding"],
                models[0] if models else None,
            ):
                chosen = self._match(candidate, models) if candidate else None
                if chosen:
                    break
        return {
            "role": role_key,
            "requested": wanted,
            "model": chosen,
            "fallback": fallback_used,
            "available": models,
        }

    def apply(self, role: str) -> str | None:
        info = self.resolve(role)
        model = info.get("model")
        if not model:
            return None
        if info["role"] in {"chat", "fast"}:
            self.llm.chat_model = model
        else:
            self.llm.model = model
            if info["role"] == "coding":
                pass
            else:
                self.llm.chat_model = self.llm.chat_model or model
        return model
