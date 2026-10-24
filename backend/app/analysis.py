"""Pure analysis functions (no web framework, no I/O) so they are easy to test.

Sign convention everywhere: error = forecast - actual.
  error > 0  -> wind was OVER-forecast  -> real shortfall, power must be bought later
  error < 0  -> wind was UNDER-forecast -> surplus was bought
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from . import timeutil as tu
from .store import DataStore


@dataclass
class Slot:
    start: datetime
    forecast: Optional[float]
    published: Optional[datetime]
    actual: Optional[float]


def day_slots(store: DataStore, day: date, cutoff: str) -> List[Slot]:
    """For each half-hour of `day`, the forecast a buyer could see at the cutoff on D-1."""
    cut = tu.cutoff_utc(day, cutoff)
    out = []
    for t in tu.delivery_slots(day):
        fc = store.forecast_asof(t, cut)
        out.append(Slot(t, fc[1] if fc else None, fc[0] if fc else None, store.actuals.get(t)))
    return out


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    """Linear-interpolated percentile (same as numpy's default). q in [0, 100]."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (k - lo)


def _r(x: Optional[float], nd: int = 1) -> Optional[float]:
    return None if x is None else round(x, nd)


def summarize(pairs: Sequence[Tuple[float, float]]) -> dict:
    """Error metrics for (forecast, actual) pairs. MAPE is deliberately omitted:
    wind output can approach zero, which makes percentage errors explode."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    errs = [f - a for f, a in pairs]
    abs_errs = [abs(e) for e in errs]
    mean_actual = sum(a for _, a in pairs) / n
    mae = sum(abs_errs) / n
    return {
        "n": n,
        "mean_actual_mw": _r(mean_actual),
        "mae_mw": _r(mae),
        "rmse_mw": _r(math.sqrt(sum(e * e for e in errs) / n)),
        "bias_mw": _r(sum(errs) / n),
        "nmae_pct": _r(100 * mae / mean_actual) if mean_actual > 0 else None,
        "p50_abs_mw": _r(percentile(abs_errs, 50)),
        "p90_abs_mw": _r(percentile(abs_errs, 90)),
        "p95_abs_mw": _r(percentile(abs_errs, 95)),
        "p95_over_mw": _r(percentile(errs, 95)),  # 1-in-20 worst over-forecast
        "over_share_pct": _r(100 * sum(1 for e in errs if e > 0) / n),
    }


def _pairs(slots: Sequence[Slot]) -> List[Tuple[float, float]]:
    return [(s.forecast, s.actual) for s in slots if s.forecast is not None and s.actual is not None]


def typical_band(store: DataStore, day: date, cutoff: str) -> Optional[dict]:
    """Empirical 5th-95th percentile of (actual - forecast), from days before `day` only
    (what a buyer could actually have known). Falls back to the other days if there is
    too little history, and says so."""
    key = ("band", day, cutoff)
    if key in store.cache:
        return store.cache[key]
    days = store.delivery_days()
    history = [d for d in days if d < day]
    basis = "previous days"
    if len(history) < 3:
        history = [d for d in days if d != day]
        basis = "other days in the period"
    diffs = [a - f for d in history for f, a in _pairs(day_slots(store, d, cutoff))]
    result = None
    if len(diffs) >= 48:
        result = {
            "lo_mw": _r(percentile(diffs, 5)),
            "hi_mw": _r(percentile(diffs, 95)),
            "days": len(history),
            "basis": basis,
        }
    store.cache[key] = result
    return result


def days_between(store: DataStore, start: date, end: date) -> List[date]:
    return [d for d in store.delivery_days() if start <= d <= end]


def accuracy(store: DataStore, start: date, end: date, cutoff: str) -> dict:
    key = ("acc", start, end, cutoff)
    if key in store.cache:
        return store.cache[key]

    days = days_between(store, start, end)
    all_pairs: List[Tuple[float, float]] = []
    by_day, hour_pairs, level_pairs = [], {}, {}
    band_width_mw = 2500

    for d in days:
        slots = day_slots(store, d, cutoff)
        pairs = _pairs(slots)
        if not pairs:
            continue
        all_pairs += pairs
        s = summarize(pairs)
        by_day.append({"day": d.isoformat(), **{k: s[k] for k in ("n", "mae_mw", "rmse_mw", "bias_mw", "mean_actual_mw")}})
        for slot in slots:
            if slot.forecast is None or slot.actual is None:
                continue
            hour_pairs.setdefault(tu.local_hour(slot.start), []).append((slot.forecast, slot.actual))
            level_pairs.setdefault(int(slot.actual // band_width_mw), []).append((slot.forecast, slot.actual))

    by_hour = []
    for h in sorted(hour_pairs):
        s = summarize(hour_pairs[h])
        by_hour.append({"hour": h, "n": s["n"], "mae_mw": s["mae_mw"], "bias_mw": s["bias_mw"]})

    by_level = []
    for b in sorted(level_pairs):
        s = summarize(level_pairs[b])
        lo, hi = b * band_width_mw, (b + 1) * band_width_mw
        by_level.append(
            {"label": f"{lo / 1000:.1f}\u2013{hi / 1000:.1f} GW", "from_mw": lo, "to_mw": hi,
             "n": s["n"], "mae_mw": s["mae_mw"], "bias_mw": s["bias_mw"]}
        )

    diffs = [a - f for f, a in all_pairs]
    result = {
        "period": {"from": start.isoformat(), "to": end.isoformat(), "days": len(by_day)},
        "cutoff": cutoff,
        "overall": summarize(all_pairs),
        "error_band": {"lo_mw": _r(percentile(diffs, 5)), "hi_mw": _r(percentile(diffs, 95))} if diffs else None,
        "by_day": by_day,
        "by_hour": by_hour,
        "by_level": by_level,
    }
    store.cache[key] = result
    return result


def horizon_analysis(store: DataStore, start: date, end: date, cutoff: str,
                     bucket_h: int = 6, max_h: int = 72) -> dict:
    """Error by lead time: every forecast ever published for the target, grouped by how
    many hours before delivery it was published. Shows how much accuracy is gained by
    waiting, and which lead times the chosen cutoff actually uses."""
    key = ("hor", start, end, cutoff, bucket_h, max_h)
    if key in store.cache:
        return store.cache[key]

    days = days_between(store, start, end)
    buckets: Dict[int, List[Tuple[float, float]]] = {}
    for d in days:
        for t in tu.delivery_slots(d):
            actual = store.actuals.get(t)
            if actual is None:
                continue
            for pub, mw in store.forecast_history(t):
                h = (t - pub).total_seconds() / 3600
                if 0 <= h < max_h:
                    buckets.setdefault(int(h // bucket_h), []).append((mw, actual))

    window = None
    if days:
        slots = tu.delivery_slots(days[0])
        cut = tu.cutoff_utc(days[0], cutoff)
        window = [_r((slots[0] - cut).total_seconds() / 3600), _r((slots[-1] - cut).total_seconds() / 3600)]

    out = []
    for b in sorted(buckets):
        s = summarize(buckets[b])
        lo, hi = b * bucket_h, (b + 1) * bucket_h
        out.append({
            "label": f"{lo}\u2013{hi}h", "from_h": lo, "to_h": hi, "n": s["n"],
            "mae_mw": s["mae_mw"], "rmse_mw": s["rmse_mw"], "bias_mw": s["bias_mw"],
            "in_decision_window": bool(window and lo < window[1] and hi > window[0]),
        })
    result = {"cutoff": cutoff, "decision_window_h": window, "buckets": out}
    store.cache[key] = result
    return result
