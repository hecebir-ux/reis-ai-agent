from __future__ import annotations

from dataclasses import dataclass, field


CATEGORIES = (
    "CHAT",
    "QUESTION",
    "TASK",
    "CODING",
    "DEBUG",
    "RESEARCH",
    "FILE_OPERATION",
    "SYSTEM_OPERATION",
    "BROWSER_TASK",
    "PROJECT_TASK",
    "AUTOMATION",
    "ANALYSIS",
    "DOCUMENT_TASK",
    "MEDIA_TASK",
    "DEPLOYMENT",
    "SELF_EVOLUTION",
)

_BUILD = {
    "yap", "yaz", "kodla", "üret", "uret", "geliştir", "gelistir",
    "oluştur", "olustur", "kur", "hazırla", "hazirla", "tasarla",
    "create", "build", "make", "develop", "code", "generate",
    "ekle", "implement", "scaffold",
}
_CHAT = {
    "kimsin", "tanıt", "tanit", "nasılsın", "nasilsin", "merhaba", "selam",
    "naber", "nedir", "anlat", "açıkla", "acikla", "hello", "hi",
    "günaydın", "gunaydin", "teşekkür", "tesekkur",
}
_DEBUG = {"debug", "hata", "düzelt", "duzelt", "bozuk", "çöktü", "coktu", "traceback"}
_RESEARCH = {"araştır", "arastir", "research", "dokümantasyon", "dokumantasyon", "nedir"}
_FILE = {"dosya", "klasör", "klasor", "sil", "kopyala", "taşı", "tasi", "oku", "yaz"}
_SYS = {"status", "durum", "modeller", "ortam", "environment", "disk", "ram"}
_BROWSER = {"tarayıcı", "tarayici", "browser", "siteye git", "tıkla", "tikla"}
_PROJECT = {"projeyi", "çalıştır", "calistir", "testleri", "readme", "zip", "git"}
_AUTO = {"zamanla", "her gün", "otomatik", "schedule"}
_DOC = {"pdf", "docx", "xlsx", "csv", "markdown"}
_MEDIA = {"görsel", "gorsel", "resim", "screenshot", "ocr", "ses", "voice"}
_DEPLOY = {"deploy", "docker", "vps", "railway", "render", "production"}
_ANALYSIS = {"analiz", "incele", "tara", "index"}


@dataclass
class IntentResult:
    primary: str
    intents: list[str] = field(default_factory=list)
    confidence: float = 0.5
    raw: str = ""


class IntentEngine:
    def classify(self, text: str) -> IntentResult:
        original = text or ""
        t = original.lower()
        words = set(t.replace("?", " ").replace("!", " ").split())
        found: list[str] = []

        if words & _CHAT and not (words & _BUILD):
            found.append("CHAT")
        if t.strip().endswith("?") or "nedir" in words or "nasıl" in words or "nasil" in words:
            found.append("QUESTION")
        if words & _BUILD or "proje" in t:
            found.append("CODING")
            found.append("PROJECT_TASK")
            found.append("TASK")
        if words & _DEBUG or "hata ekle" in t:
            found.append("DEBUG")
        if words & _RESEARCH:
            found.append("RESEARCH")
        if words & _FILE:
            found.append("FILE_OPERATION")
        if words & _SYS:
            found.append("SYSTEM_OPERATION")
        if words & _BROWSER:
            found.append("BROWSER_TASK")
        if words & _PROJECT:
            found.append("PROJECT_TASK")
        if words & _AUTO:
            found.append("AUTOMATION")
        if words & _DOC:
            found.append("DOCUMENT_TASK")
        if words & _MEDIA:
            found.append("MEDIA_TASK")
        if words & _DEPLOY:
            found.append("DEPLOYMENT")
        if words & _ANALYSIS:
            found.append("ANALYSIS")
        from core.evolution.intents import match_evolution_intent

        evo = match_evolution_intent(original)
        if evo:
            found.insert(0, "SELF_EVOLUTION")

        if not found:
            if len(words) <= 3:
                found = ["CHAT"]
            else:
                found = ["CHAT", "QUESTION"]

        # unique preserve order
        seen = []
        for item in found:
            if item not in seen:
                seen.append(item)
        primary = seen[0]
        if "SELF_EVOLUTION" in seen:
            primary = "SELF_EVOLUTION"
        elif "CODING" in seen:
            primary = "CODING"
        elif "DEBUG" in seen:
            primary = "DEBUG"
        elif "PROJECT_TASK" in seen and "CHAT" not in {primary}:
            primary = "PROJECT_TASK"
        conf = min(0.95, 0.4 + 0.15 * len(seen))
        return IntentResult(primary=primary, intents=seen, confidence=conf, raw=original)
