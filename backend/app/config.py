from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("WINDWARD_DATA_DIR", ROOT / "data"))
SAMPLE_DIR = DATA_DIR / "sample"

# Day-ahead decision cutoff, UK local time on the day before delivery.
DEFAULT_CUTOFF = "09:00"
CUTOFF_OPTIONS = ["07:00", "08:00", "09:00", "10:00", "11:00"]
