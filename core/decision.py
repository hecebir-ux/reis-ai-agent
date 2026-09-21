from __future__ import annotations

from core.intent.engine import IntentResult
from core.security import RiskLevel, classify_risk, requires_approval
import config


class DecisionEngine:
    def decide(self, text: str, intent: IntentResult) -> dict:
        primary = intent.primary
        size = "small" if len(text) < 80 else ("medium" if len(text) < 240 else "large")
        risk = classify_risk(primary, text)
        model_role = "chat"
        if primary in {"CODING", "DEBUG", "PROJECT_TASK"}:
            model_role = "coding"
        elif primary == "SELF_EVOLUTION":
            model_role = "reasoning"
        elif primary == "RESEARCH":
            model_role = "research"
        elif primary == "MEDIA_TASK":
            model_role = "vision"
        elif primary in {"QUESTION", "CHAT"}:
            model_role = "fast"
        tools = []
        if primary in {"CODING", "PROJECT_TASK", "DEBUG"}:
            tools = ["filesystem", "python", "terminal", "tester", "debugger"]
        elif primary == "FILE_OPERATION":
            tools = ["filesystem"]
        elif primary == "RESEARCH":
            tools = ["web"]
        elif primary == "BROWSER_TASK":
            tools = ["browser"]
        elif primary == "SYSTEM_OPERATION":
            tools = ["env"]
        parallel = size != "small" and primary in {"CODING", "PROJECT_TASK", "RESEARCH"}
        approve = requires_approval(risk, config.SAFE_MODE)
        return {
            "size": size,
            "risk": risk.value if isinstance(risk, RiskLevel) else str(risk),
            "model_role": model_role,
            "tools": tools,
            "parallel": parallel,
            "needs_approval": approve,
        }
