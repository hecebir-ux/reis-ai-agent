from __future__ import annotations

from typing import Callable

COMMANDS = {
    "/help": "Komut listesi",
    "/models": "Ollama modelleri",
    "/projects": "Kayıtlı projeler",
    "/tasks": "Görevler",
    "/status": "Sistem durumu",
    "/stop": "Aktif görevi durdur",
    "/pause": "Aktif görevi duraklat",
    "/resume": "Göreve devam",
    "/retry": "Son görevi tekrar dene",
    "/reset": "Sohbet bağlamını sıfırla",
    "/memory": "Bellek araması",
    "/settings": "Ayar özeti",
    "/tools": "Araç listesi",
    "/logs": "Son log satırları",
    "/env": "Ortam kontrolü",
    "/evolve": "Self-evolution döngüsü",
    "/diagnose": "Kendi kodunu tara",
    "/boot": "Tüm self-* sistemlerini yeniden aktifleştir",
}


def parse_command(text: str) -> tuple[str, str] | None:
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return None
    parts = raw.split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    return name, arg
