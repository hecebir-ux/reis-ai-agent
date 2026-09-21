from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any

import config
from core.llm_client import OllamaClient


def _run(cmd: list[str]) -> dict[str, Any]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=12, encoding="utf-8", errors="replace")
        out = (r.stdout or r.stderr or "").strip().splitlines()
        return {"ok": r.returncode == 0, "version": out[0] if out else "", "detail": (r.stderr or "")[:200]}
    except Exception as e:
        return {"ok": False, "version": "", "detail": str(e)}


def environment_report(llm: OllamaClient | None = None) -> dict[str, Any]:
    llm = llm or OllamaClient()
    health = llm.health_check()
    ram = {}
    try:
        import psutil  # type: ignore
        ram = {"total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2), "percent": psutil.virtual_memory().percent}
    except Exception:
        ram = {"total_gb": None, "percent": None}

    disk = shutil.disk_usage(str(config.BASE_DIR))
    tools = {
        "windows": {"ok": os.name == "nt", "version": platform.platform()},
        "python": _run(["python", "--version"]),
        "git": _run(["git", "--version"]),
        "node": _run(["node", "--version"]),
        "npm": _run(["npm", "--version"]),
        "powershell": {"ok": True, "version": "Windows PowerShell"},
        "ffmpeg": _run(["ffmpeg", "-version"]),
        "docker": _run(["docker", "--version"]),
        "ollama": {"ok": bool(health.get("ok")), "version": ", ".join(health.get("models", [])[:6]), "detail": health.get("error", "")},
    }
    missing = [name for name, info in tools.items() if not info.get("ok") and name not in {"ffmpeg", "docker"}]
    optional_missing = [name for name in ("ffmpeg", "docker") if not tools[name].get("ok")]
    return {
        "ok": tools["python"]["ok"] and tools["ollama"]["ok"],
        "tools": tools,
        "missing": missing,
        "optional_missing": optional_missing,
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "ram": ram,
        "internet": _internet(),
        "gpu": _gpu(),
    }


def _internet() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen("https://example.com", timeout=3)
        return True
    except Exception:
        return False


def _gpu() -> str:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return "algılanamadı"


def format_env_report(report: dict[str, Any]) -> str:
    lines = ["Ortam kontrolü:"]
    for name, info in report["tools"].items():
        mark = "OK" if info.get("ok") else "YOK"
        extra = info.get("version") or info.get("detail") or ""
        lines.append(f"  [{mark}] {name}: {extra}")
    if report["missing"]:
        lines.append("Eksik zorunlu araçlar: " + ", ".join(report["missing"]))
    if report["optional_missing"]:
        lines.append("Opsiyonel eksikler: " + ", ".join(report["optional_missing"]))
    lines.append(f"Disk boş: {report['disk_free_gb']} GB")
    lines.append(f"İnternet: {'var' if report['internet'] else 'yok / kısıtlı'}")
    lines.append(f"GPU: {report['gpu']}")
    return "\n".join(lines)
