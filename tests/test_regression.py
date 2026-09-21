#!/usr/bin/env python3
"""Yeni özellik sonrası eski süiti çalıştır."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
py = HERE / ".venv" / "Scripts" / "python.exe"
exe = str(py if py.exists() else sys.executable)

old = subprocess.run([exe, str(HERE / "tests" / "REIS_OTOMATIK_TEST.py")], cwd=str(HERE))
new = subprocess.run([exe, str(HERE / "tests" / "test_reis_max.py")], cwd=str(HERE))
sys.exit(0 if old.returncode == 0 and new.returncode == 0 else 1)
