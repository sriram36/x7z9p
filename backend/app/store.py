"""In-memory data store.

The January 2026 dataset is small (a few 100k rows), so it is loaded once at start-up
into plain dicts and sorted lists. Pure standard library: no pandas/numpy, which keeps
the Vercel function small and cold starts fast.
"""
from __future__ import annotations

import csv
import gzip
import json
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from . import timeutil as tu

ACTUALS_FILE = "actuals_wind.csv"
FORECASTS_FILE = "windfor.csv.gz"
META_FILE = "meta.json"


class DataStore:
    def __init__(
        self,
        actuals: Dict[datetime, float],
        forecasts: Iterable[Tuple[datetime, datetime, float]],
        meta: Optional[dict] = None,
        is_sample: bool = False,
    ):
        self.actuals = dict(actuals)
        grouped: Dict[datetime, Dict[datetime, float]] = defaultdict(dict)
        for target, publish, mw in forecasts:
            grouped[target][publish] = mw  # a re-published identical key keeps the last value
        self.pub: Dict[datetime, List[datetime]] = {}
        self.val: Dict[datetime, List[float]] = {}
        for target, by_pub in grouped.items():
            items = sorted(by_pub.items())
            self.pub[target] = [p for p, _ in items]
            self.val[target] = [v for _, v in items]
        self.meta = meta or {}
        self.is_sample = is_sample
        self.cache: dict = {}

    def _effective_target(self, target: datetime) -> datetime:
        if target not in self.pub and target.minute != 0:
            floored = target.replace(minute=0, second=0)
            if floored in self.pub:
                return floored
        return target

    def forecast_asof(self, target: datetime, cutoff: datetime) -> Optional[Tuple[datetime, float]]:
        """Latest forecast for `target` published at or before `cutoff`.
        
        If `target` has no exact match (e.g. half-hourly slot :30) and the forecast dataset
        is hourly (e.g. Elexon WINDFOR), falls back to the hour's forecast.
        """
        key = self._effective_target(target)
        pubs = self.pub.get(key)
        if not pubs:
            return None
        i = bisect_right(pubs, cutoff)
        if i == 0:
            return None
        return pubs[i - 1], self.val[key][i - 1]

    def forecast_history(self, target: datetime) -> List[Tuple[datetime, float]]:
        key = self._effective_target(target)
        return list(zip(self.pub.get(key, []), self.val.get(key, [])))

    def delivery_days(self, min_slots: int = 20) -> List[date]:
        counts: Dict[date, int] = defaultdict(int)
        for t in self.pub:
            counts[tu.local_date(t)] += 1
        return sorted(d for d, c in counts.items() if c >= min_slots)


def load_store(data_dir: Path, is_sample: bool = False) -> Optional[DataStore]:
    actual_path = data_dir / ACTUALS_FILE
    forecast_path = data_dir / FORECASTS_FILE
    if not (actual_path.exists() and forecast_path.exists()):
        return None

    actuals: Dict[datetime, float] = {}
    with open(actual_path, newline="") as f:
        for row in csv.DictReader(f):
            actuals[tu.parse_utc(row["start_time"])] = float(row["generation_mw"])

    forecasts = []
    with gzip.open(forecast_path, "rt", newline="") as f:
        for row in csv.DictReader(f):
            forecasts.append(
                (tu.parse_utc(row["start_time"]), tu.parse_utc(row["publish_time"]), float(row["generation_mw"]))
            )

    meta_path = data_dir / META_FILE
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return DataStore(actuals, forecasts, meta, is_sample)
