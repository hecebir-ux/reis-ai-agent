from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvolutionIntent:
    kind: str
    confidence: float
    raw: str


_MAP: list[tuple[str, tuple[str, ...]]] = [
    (
        "full_evolve",
        (
            "kendini geliştir",
            "kendini gelistir",
            "kendini iyileştir",
            "self evolution",
            "kendini analiz et",
            "kendini analiz",
            "eksiklerini bul",
            "daha sağlam",
        ),
    ),
    (
        "diagnose",
        ("kendini analiz", "analiz et", "eksiklerini bul", "diagnostics"),
    ),
    (
        "faster",
        ("daha hızlı", "daha hizli", "hızlı cevap", "hizli cevap", "optimize"),
    ),
    (
        "typos",
        ("yazım hatalarını azalt", "yazim hatalarini azalt", "yazım hatası"),
    ),
    (
        "files",
        ("dosya yönetimini geliştir", "dosya yonetimini gelistir", "dosya yönetimi"),
    ),
    (
        "new_feature",
        ("yeni bir özellik ekle", "yeni ozellik", "yeni özellik ekle", "feature ekle"),
    ),
    (
        "fix_error",
        ("bu hatayı çöz", "bu hatayi coz", "hatayı çöz", "self heal", "düzelt bu hata"),
    ),
    (
        "improve_project",
        ("bu projeyi geliştir", "bu projeyi gelistir", "projeyi geliştir"),
    ),
    (
        "system_check",
        ("bilgisayarımı kontrol et", "bilgisayarimi kontrol et", "sistemi kontrol"),
    ),
    (
        "desktop",
        ("masaüstümü düzenle", "masaustumu duzenle", "masaüstü düzenle", "desktop organize"),
    ),
    (
        "self_test",
        ("bu projeyi kendin test et", "kendini test et", "kendini test", "self test"),
    ),
]


def match_evolution_intent(text: str) -> EvolutionIntent | None:
    raw = (text or "").strip()
    t = raw.lower()
    if not t:
        return None
    if "kendini" in t and any(k in t for k in ("geliştir", "gelistir", "analiz", "iyileştir", "iyilestir", "test")):
        evolve_markers = (
            "geliştir", "gelistir", "iyileştir", "iyilestir", "özellik", "ozellik",
            "uygula", "sağlam", "saglam", "eksik",
        )
        if "analiz" in t and any(k in t for k in evolve_markers):
            kind = "full_evolve"
        elif "analiz" in t:
            kind = "diagnose"
        elif "test" in t and "geliştir" not in t and "gelistir" not in t:
            kind = "self_test"
        else:
            kind = "full_evolve"
        return EvolutionIntent(kind=kind, confidence=0.92, raw=raw)
    for kind, phrases in _MAP:
        for p in phrases:
            if p in t:
                return EvolutionIntent(kind=kind, confidence=0.88, raw=raw)
    if "güncel teknik" in t or "guncel teknik" in t or "web araştırm" in t or "web arastir" in t:
        return EvolutionIntent(kind="research", confidence=0.8, raw=raw)
    return None
