"""REIS AI self-evolution package — local, IDE-independent."""

from core.evolution.intents import match_evolution_intent
from core.evolution.loop import EvolutionLoop
from core.evolution.boot import boot_all, format_boot_report

__all__ = ["EvolutionLoop", "match_evolution_intent", "boot_all", "format_boot_report"]
