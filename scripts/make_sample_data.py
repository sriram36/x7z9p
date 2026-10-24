#!/usr/bin/env python3
"""Generate SYNTHETIC data (data/sample/) so the app can run without network access.
The app shows a banner whenever it is serving this. Never submit with this data."""
from __future__ import annotations

import csv
import gzip
import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import timeutil as tu  # noqa: E402


def main() -> None:
    rnd = random.Random(7)
    out = ROOT / "data" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    first, last = date(2026, 1, 2), date(2026, 2, 1)
    start = tu.delivery_slots(first)[0]
    end = tu.delivery_slots(last)[-1] + tu.SLOT

    actual, x, t = {}, 0.0, start
    while t < end:
        x = 0.985 * x + rnd.gauss(0, 0.16)  # slow weather-like drift
        actual[t] = round(max(150.0, min(13500.0, 5200 + 3600 * x * 1.3)), 0)
        t += tu.SLOT

    rows, errs = [], {}
    pub = start - timedelta(hours=72)
    pub = pub.replace(minute=0)
    while pub < end:
        t = pub
        while t < pub + timedelta(hours=72):
            if t in actual and t >= pub:
                lead = (t - pub).total_seconds() / 3600
                # persistent per-(target, 6h-block) error that grows with lead time
                k = (t, int(lead // 6))
                errs.setdefault(k, rnd.gauss(0, 1))
                noise = errs[k] * (180 + 38 * lead) + rnd.gauss(0, 60) + 40
                rows.append((tu.iso(t), tu.iso(pub), round(max(0.0, actual[t] + noise), 0)))
            t += tu.SLOT
        pub += timedelta(hours=1)

    with open(out / "actuals_wind.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["start_time", "generation_mw"])
        for k in sorted(actual):
            w.writerow([tu.iso(k), actual[k]])
    with gzip.open(out / "windfor.csv.gz", "wt", newline="") as f:
        w = csv.writer(f); w.writerow(["start_time", "publish_time", "generation_mw"])
        w.writerows(rows)
    (out / "meta.json").write_text(json.dumps({"note": "SYNTHETIC sample data", "rows": {"actuals": len(actual), "forecasts": len(rows)}}))
    print(f"sample written: {len(actual)} actuals, {len(rows)} forecasts -> {out}")


if __name__ == "__main__":
    main()
