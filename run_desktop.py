from __future__ import annotations

import sys
from pathlib import Path

# Ensure desktop_app package is importable
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "desktop_app"))

from autoblog_desktop.main import run


if __name__ == "__main__":
    raise SystemExit(run())
