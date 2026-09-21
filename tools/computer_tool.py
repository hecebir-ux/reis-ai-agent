from __future__ import annotations

import json
import subprocess
from pathlib import Path

import config
from core.security import RiskLevel, classify_risk, requires_approval


class ComputerAgent:
    """Controlled desktop primitives. High/critical actions require approval."""

    def screenshot(self, dest: str | None = None, approved: bool = False) -> dict:
        dest_path = Path(dest or (config.WORKSPACE_DIR / "_reis_screenshot.png"))
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        ps = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save('{str(dest_path).replace("'", "''")}')
$g.Dispose(); $bmp.Dispose()
"""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=20,
            )
            ok = r.returncode == 0 and dest_path.exists()
            return {"success": ok, "path": str(dest_path) if ok else "", "stderr": r.stderr, "risk": RiskLevel.LOW.value}
        except Exception as e:
            return {"success": False, "error": str(e), "risk": RiskLevel.LOW.value}

    def clipboard_get(self) -> dict:
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=10,
            )
            return {"success": r.returncode == 0, "text": (r.stdout or "")[:4000]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def launch_app(self, command: str, approved: bool = False) -> dict:
        risk = classify_risk("launch_app", command)
        if requires_approval(risk, True) and not approved:
            return {"success": False, "needs_approval": True, "risk": risk.value}
        try:
            subprocess.Popen(command, shell=True)
            return {"success": True, "command": command, "risk": risk.value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mouse_keyboard_stub(self) -> dict:
        return {
            "success": True,
            "enabled": False,
            "note": "Mouse/keyboard enjeksiyonu güvenlik katmanından onay ile açılacak.",
            "risk": RiskLevel.HIGH.value,
        }
