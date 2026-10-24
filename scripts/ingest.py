#!/usr/bin/env python3
"""Download wind actuals (FUELHH) and wind forecasts (WINDFOR) from Elexon BMRS and
write the compact snapshot the app serves from.

Scope: purchase decisions made in January 2026 -> delivery days 2 Jan .. 1 Feb 2026
(day-ahead: a decision on day D-1 buys for day D). Override with --decision-start/--decision-end.

Only WINDFOR rows with 0 <= lead time <= --max-horizon-h are kept, and only for targets in
the delivery window. Standard library only; no API key needed.

    python scripts/ingest.py
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import timeutil as tu  # noqa: E402

BASE = "https://data.elexon.co.uk/bmrs/api/v1"


def fetch(path: str, params: list, retries: int = 4) -> list:
    url = f"{BASE}{path}?{urllib.parse.urlencode(params + [('format', 'json')])}"
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "windward-ingest/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.load(resp)
            return payload["data"] if isinstance(payload, dict) and "data" in payload else payload
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                raise SystemExit(f"Failed after {retries} attempts: {url}\n  {exc}")
            wait = 2 ** attempt
            print(f"  retry {attempt}/{retries - 1} in {wait}s ({exc})")
            time.sleep(wait)
    return []


def chunks(start: date, end: date, step_days: int):
    d = start
    while d <= end:
        yield d, min(d + timedelta(days=step_days - 1), end)
        d += timedelta(days=step_days)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--decision-start", type=date.fromisoformat, default=date(2026, 1, 1))
    ap.add_argument("--decision-end", type=date.fromisoformat, default=date(2026, 1, 31))
    ap.add_argument("--max-horizon-h", type=int, default=72)
    ap.add_argument("--out", type=Path, default=ROOT / "data")
    args = ap.parse_args()

    d_start = args.decision_start + timedelta(days=1)  # first delivery day
    d_end = args.decision_end + timedelta(days=1)  # last delivery day
    win_start = tu.delivery_slots(d_start)[0]
    win_end = tu.delivery_slots(d_end)[-1] + tu.SLOT  # exclusive
    print(f"Decisions {args.decision_start}..{args.decision_end}  ->  delivery {d_start}..{d_end}")

    # ---- actuals (FUELHH, WIND) -------------------------------------------------
    actuals = {}
    for a, b in chunks(d_start - timedelta(days=1), d_end + timedelta(days=1), 7):
        print(f"FUELHH {a}..{b}")
        rows = fetch("/datasets/FUELHH/stream", [("settlementDateFrom", a.isoformat()),
                                                  ("settlementDateTo", b.isoformat()), ("fuelType", "WIND")])
        for r in rows:
            if r.get("fuelType") != "WIND":
                continue
            t = tu.parse_utc(r["startTime"])
            if win_start <= t < win_end:
                actuals[t] = float(r["generation"])
    if not actuals:
        raise SystemExit("No FUELHH wind rows returned - check connectivity / date range.")

    # ---- forecasts (WINDFOR) ----------------------------------------------------
    forecasts = {}
    pub_from = (win_start - timedelta(hours=args.max_horizon_h)).date()
    pub_to = win_end.date()
    for a, b in chunks(pub_from, pub_to, 1):
        print(f"WINDFOR published {a}")
        rows = fetch("/datasets/WINDFOR/stream", [("publishDateTimeFrom", f"{a.isoformat()}T00:00:00Z"),
                                                   ("publishDateTimeTo", f"{b.isoformat()}T23:59:59Z")])
        for r in rows:
            t, p = tu.parse_utc(r["startTime"]), tu.parse_utc(r["publishTime"])
            lead_h = (t - p).total_seconds() / 3600
            if win_start <= t < win_end and 0 <= lead_h <= args.max_horizon_h:
                forecasts[(t, p)] = float(r["generation"])
    if not forecasts:
        raise SystemExit("No WINDFOR rows returned - check connectivity / date range.")

    # ---- write -------------------------------------------------------------------
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "actuals_wind.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["start_time", "generation_mw"])
        for t in sorted(actuals):
            w.writerow([tu.iso(t), actuals[t]])
    with gzip.open(args.out / "windfor.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["start_time", "publish_time", "generation_mw"])
        for (t, p) in sorted(forecasts):
            w.writerow([tu.iso(t), tu.iso(p), forecasts[(t, p)]])
    meta = {
        "dataset_actual": "FUELHH (fuelType=WIND)", "dataset_forecast": "WINDFOR",
        "decision_window": [args.decision_start.isoformat(), args.decision_end.isoformat()],
        "delivery_window": [d_start.isoformat(), d_end.isoformat()],
        "max_horizon_h": args.max_horizon_h,
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": {"actuals": len(actuals), "forecasts": len(forecasts)},
        "attribution": "Contains BMRS data \u00a9 Elexon Limited copyright and database right 2026.",
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2))

    n_days = (d_end - d_start).days + 1
    print(f"\nactuals: {len(actuals)} rows (expect ~{n_days * 48})   forecasts: {len(forecasts)} rows")
    missing = [t for t in tu.delivery_slots(d_start) if t not in actuals]
    if missing:
        print(f"WARNING: {len(missing)} missing actual slots on {d_start}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
