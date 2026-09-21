"""Voice pipeline architecture. Disabled until VOICE_ENABLED=true."""
from __future__ import annotations

import config


class VoicePipeline:
    def enabled(self) -> bool:
        return bool(config.VOICE_ENABLED)

    def status(self) -> dict:
        return {
            "enabled": self.enabled(),
            "flow": ["VOICE_INPUT", "SPEECH_TO_TEXT", "REIS_AI", "TEXT_TO_SPEECH"],
            "language": "tr",
            "note": "UI'dan açılıp kapatılacak. İlk sürümde kapalı.",
        }
