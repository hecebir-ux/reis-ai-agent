import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "workspace"
MEMORY_DIR = BASE_DIR / "memory"
LOGS_DIR = BASE_DIR / "logs"
DATABASE_DIR = BASE_DIR / "database"
PLUGINS_DIR = BASE_DIR / "plugins"
PROJECTS_DIR = BASE_DIR / "projects"
BACKUPS_DIR = BASE_DIR / "backups"
CACHE_DIR = BASE_DIR / "cache"

for d in [WORKSPACE_DIR, MEMORY_DIR, LOGS_DIR, DATABASE_DIR, PLUGINS_DIR, PROJECTS_DIR, BACKUPS_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen3:8b")
OLLAMA_CODE_MODEL = os.getenv("OLLAMA_CODE_MODEL", "qwen2.5-coder:latest")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llama3.2-vision:latest")
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "llama3.2:latest")
OLLAMA_RESEARCH_MODEL = os.getenv("OLLAMA_RESEARCH_MODEL", "qwen3:8b")
OLLAMA_REASONING_MODEL = os.getenv("OLLAMA_REASONING_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.3"))
OLLAMA_CTX_WINDOW = int(os.getenv("OLLAMA_CTX_WINDOW", "4096"))
OLLAMA_MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "2"))

MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
MAX_DEBUG_ATTEMPTS = int(os.getenv("MAX_DEBUG_ATTEMPTS", "5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "3"))
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "120"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MEMORY_FILE = MEMORY_DIR / "sessions.json"
SQLITE_PATH = DATABASE_DIR / "reis_max.db"

def _flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}

MEMORY_ENABLED = _flag("MEMORY_ENABLED", "true")
WEB_ENABLED = _flag("WEB_ENABLED", "true")
VOICE_ENABLED = _flag("VOICE_ENABLED", "false")
VISION_ENABLED = _flag("VISION_ENABLED", "true")
BROWSER_ENABLED = _flag("BROWSER_ENABLED", "false")
SAFE_MODE = _flag("SAFE_MODE", "true")
API_ENABLED = _flag("API_ENABLED", "false")
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8741"))
API_TOKEN = os.getenv("API_TOKEN", "")
GIT_PUSH_REQUIRES_APPROVAL = _flag("GIT_PUSH_REQUIRES_APPROVAL", "true")
EVOLUTION_GIT_COMMIT = _flag("EVOLUTION_GIT_COMMIT", "false")
EVOLUTION_MAX_HEAL = int(os.getenv("EVOLUTION_MAX_HEAL", "3"))
EVOLUTION_BOOT = _flag("EVOLUTION_BOOT", "true")
EVOLUTION_BOOT_RESUME = _flag("EVOLUTION_BOOT_RESUME", "true")
UI_ENABLED = _flag("UI_ENABLED", "true")
UI_HOST = os.getenv("UI_HOST", "127.0.0.1")
UI_PORT = int(os.getenv("UI_PORT", "8765"))
UI_OPEN_BROWSER = _flag("UI_OPEN_BROWSER", "true")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_IDS = os.getenv("TELEGRAM_ALLOWED_IDS", "")
TELEGRAM_TIMEOUT = int(os.getenv("TELEGRAM_TIMEOUT", "60"))
TELEGRAM_AUTO_START = _flag("TELEGRAM_AUTO_START", "true")

# Model routing (override via env)
MODEL_ROUTES = {
    "FAST": OLLAMA_FAST_MODEL,
    "CHAT": OLLAMA_CHAT_MODEL,
    "CODING": OLLAMA_CODE_MODEL,
    "REASONING": OLLAMA_REASONING_MODEL,
    "ANALYSIS": OLLAMA_REASONING_MODEL,
    "RESEARCH": OLLAMA_RESEARCH_MODEL,
    "VISION": OLLAMA_VISION_MODEL,
    "REVIEW": os.getenv("OLLAMA_REVIEW_MODEL", OLLAMA_REASONING_MODEL),
}

SAFE_ROOTS = [
    str(WORKSPACE_DIR),
    str(BASE_DIR),
]

DANGEROUS_PATTERNS = [
    r"^[A-Z]:\\Windows\\",
    r"^[A-Z]:\\Program Files",
    r"^[A-Z]:\\Program Files \(x86\)",
    r"^[A-Z]:\\Users\\[^\\]+\\AppData\\Local\\Microsoft",
    r"^[A-Z]:\\Users\\[^\\]+\\AppData\\Roaming\\Microsoft",
    r"\.sys$",
    r"\.dll$",
    r"C:\\Windows\\System32",
]

DANGEROUS_COMMANDS = [
    "format",
    "del /f /s /q",
    "rmdir /s /q",
    "rd /s /q",
    "diskpart",
    "reg delete",
    "shutdown",
    "taskkill /f /im explorer.exe",
]

SYSTEM_PROMPT = """Sen REIS AI'sin, Windows 11 üzerinde çalışan otonom bir yazılım geliştirme ajanısın.

Görev döngün:
1. KULLANICI HEDEFİ → Plan çıkar
2. PLAN → Adım adım yapılacakları belirle
3. KODLA → Python, JS, HTML vb. dosyaları workspace içinde oluştur
4. ÇALIŞTIR → terminal komutları ile test et
5. HATA VARSA → Analiz et, düzelt, tekrar test et
6. BAŞARILI → Son raporu yaz

ÖNEMLİ KURALLAR:
- Sadece REIS_AI_AGENT/workspace klasörü içinde proje oluştur
- Sistem dosyalarına dokunma
- Hataları kendi başına çözmeye çalış, hata mesajlarını dikkatlice oku
- Kod yazarken temiz mimari, hata yönetimi ve logging kullan
- Her test sonrası exit code, stdout, stderr değerlendir
- Maksimum 10 iteration içinde sonuca ulaş
"""
