from __future__ import annotations

from typing import Any, Callable

from core.metrics import metrics
from core.evolution.self_benchmark import SelfBenchmark


class SelfOptimizer:
    def __init__(self):
        self.bench = SelfBenchmark()

    def snapshot(self) -> dict[str, Any]:
        return metrics.snapshot()

    def optimize_callable(self, name: str, current: Callable[[], Any], candidate: Callable[[], Any]) -> dict[str, Any]:
        old = self.bench.measure(current, rounds=3)
        new = self.bench.measure(candidate, rounds=3)
        cmp = self.bench.compare(old, new)
        if not cmp["accept"]:
            return {"ok": False, "accepted": False, "reason": "no improvement", "old": old, "new": new, "compare": cmp, "name": name}
        return {"ok": True, "accepted": True, "old": old, "new": new, "compare": cmp, "name": name}

    def advise(self) -> list[str]:
        snap = metrics.snapshot()
        tips = []
        if (snap.get("avg_ollama_s") or 0) > 8:
            tips.append("FAST model (llama3.2) sohbet için kullanılsın; coder sadece kodda.")
        if (snap.get("error_rate") or 0) > 0.2:
            tips.append("Hata oranı yüksek: self-heal + knowledge memory kontrol et.")
        if (snap.get("retries") or 0) > 5:
            tips.append("Retry sayısı yüksek: timeout ve model router fallback gözden geçir.")
        if not tips:
            tips.append("Ölçülen darboğaz yok; FAST model varsayılan sohbet için yeterli.")
        return tips
