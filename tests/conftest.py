import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def beispiel(name: str) -> str:
    return next((ROOT / "beispiele").glob(f"{name}*.txt")).read_text(encoding="utf-8")
