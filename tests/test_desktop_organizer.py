import sys
from pathlib import Path
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.desktop_organizer import organize

def main():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "a.txt").write_text("x", encoding="utf-8")
        (p / "b.png").write_bytes(b"x")
        r = organize(p, dry_run=True)
        assert r["ok"] and r["count"] == 2, r
        r2 = organize(p, dry_run=False)
        assert r2["ok"]
        assert (p / "Documents" / "a.txt").exists()
        assert (p / "Images" / "b.png").exists()
    print("DESKTOP_ORGANIZER_OK")

if __name__ == "__main__":
    main()
