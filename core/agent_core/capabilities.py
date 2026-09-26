"""Capability Registry — REIS AI's real awareness of what it can actually do.

Instead of *claiming* to have tools, the registry probes the live environment
(binaries, Python packages, the Ollama server, disk/RAM) and reports each
capability's availability, version and health. Anything required-but-missing is
surfaced as a capability gap so the agent (or the user) knows the true limits.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

import config


@dataclass
class Capability:
    name: str
    available: bool
    version: str = ""
    detail: str = ""
    optional: bool = False
    category: str = "tool"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "version": self.version,
            "detail": self.detail,
            "optional": self.optional,
            "category": self.category,
        }


def _probe_binary(binary: str, version_args: list[str] | None = None) -> tuple[bool, str]:
    path = shutil.which(binary)
    if not path:
        return False, ""
    args = version_args if version_args is not None else ["--version"]
    try:
        r = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=8,
            encoding="utf-8",
            errors="replace",
        )
        out = (r.stdout or r.stderr or "").strip().splitlines()
        return True, (out[0] if out else path)
    except Exception:
        # Binary exists on PATH but did not answer --version; still available.
        return True, path


def _probe_python_pkg(module: str) -> tuple[bool, str]:
    try:
        mod = __import__(module)
        return True, getattr(mod, "__version__", "")
    except Exception:
        return False, ""


class CapabilityRegistry:
    """Detects and caches the real capabilities of the running environment."""

    # (name, binary, version_args, optional, category)
    _BINARIES = [
        ("git", "git", None, False, "vcs"),
        ("github_cli", "gh", ["--version"], True, "vcs"),
        ("python", "python", ["--version"], False, "runtime"),
        ("pip", "pip", ["--version"], False, "runtime"),
        ("node", "node", ["--version"], True, "runtime"),
        ("npm", "npm", ["--version"], True, "runtime"),
        ("docker", "docker", ["--version"], True, "deployment"),
        ("ffmpeg", "ffmpeg", ["-version"], True, "media"),
        ("ollama", "ollama", ["--version"], False, "llm"),
        ("zstd", "zstd", ["--version"], True, "system"),
        ("curl", "curl", ["--version"], True, "system"),
    ]

    # (name, python module, optional)
    _PY_PACKAGES = [
        ("requests", "requests", False),
        ("dotenv", "dotenv", False),
        ("bs4", "bs4", True),
        ("lxml", "lxml", True),
        ("rich", "rich", True),
    ]

    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm
        self._cache: dict[str, Capability] | None = None

    def scan(self, force: bool = False) -> dict[str, Capability]:
        if self._cache is not None and not force:
            return self._cache
        caps: dict[str, Capability] = {}

        for name, binary, vargs, optional, category in self._BINARIES:
            ok, version = _probe_binary(binary, vargs)
            caps[name] = Capability(name, ok, version, optional=optional, category=category)

        for name, module, optional in self._PY_PACKAGES:
            ok, version = _probe_python_pkg(module)
            caps[name] = Capability(
                name, ok, version, optional=optional, category="python-package"
            )

        # Ollama server + installed models (live health, not just the binary).
        caps["ollama_server"] = self._probe_ollama()

        # SQLite is always available via the stdlib but report it explicitly.
        try:
            import sqlite3  # noqa: F401

            caps["sqlite"] = Capability("sqlite", True, "", category="database")
        except Exception:
            caps["sqlite"] = Capability("sqlite", False, category="database")

        caps["filesystem"] = Capability("filesystem", True, "", category="core")
        caps["terminal"] = Capability("terminal", True, "", category="core")

        self._cache = caps
        return caps

    def _probe_ollama(self) -> Capability:
        health = None
        if self.llm is not None and hasattr(self.llm, "health_check"):
            try:
                health = self.llm.health_check()
            except Exception:
                health = None
        if health is None:
            try:
                import requests

                base = getattr(config, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
                r = requests.get(f"{base}/api/tags", timeout=5)
                models = [m["name"] for m in r.json().get("models", [])] if r.ok else []
                health = {"ok": r.ok, "models": models}
            except Exception as e:
                health = {"ok": False, "models": [], "error": str(e)}
        models = health.get("models", []) if health else []
        ok = bool(health and health.get("ok"))
        return Capability(
            "ollama_server",
            ok,
            version=", ".join(models[:6]),
            detail=("online" if ok else (health.get("error", "offline") if health else "offline")),
            category="llm",
        )

    def gaps(self, force: bool = False) -> list[str]:
        """Return names of required capabilities that are unavailable."""
        return [
            name
            for name, cap in self.scan(force=force).items()
            if not cap.available and not cap.optional
        ]

    def summary(self, force: bool = False) -> dict[str, Any]:
        caps = self.scan(force=force)
        available = [c.name for c in caps.values() if c.available]
        missing_optional = [c.name for c in caps.values() if not c.available and c.optional]
        return {
            "capabilities": {name: cap.to_dict() for name, cap in caps.items()},
            "available": available,
            "gaps": self.gaps(force=False),
            "missing_optional": missing_optional,
            "count": len(caps),
            "available_count": len(available),
        }

    def format_report(self, force: bool = False) -> str:
        caps = self.scan(force=force)
        lines = ["REIS AI — Capability Registry"]
        for cap in sorted(caps.values(), key=lambda c: (not c.available, c.category, c.name)):
            mark = "✅" if cap.available else ("➖" if cap.optional else "❌")
            extra = f" — {cap.version}" if cap.version else ""
            lines.append(f"  {mark} {cap.name} ({cap.category}){extra}")
        gaps = self.gaps(force=False)
        if gaps:
            lines.append("Kritik eksik capability: " + ", ".join(gaps))
        else:
            lines.append("Kritik eksik capability yok.")
        return "\n".join(lines)
