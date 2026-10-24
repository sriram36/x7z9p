from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import analysis, config, timeutil as tu
from .store import DataStore, load_store

app = FastAPI(title="Windward API", version="1.0.0", description="GB day-ahead wind forecast desk")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

CUTOFF = Query(config.DEFAULT_CUTOFF, pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
               description="HH:MM UK time on the day before delivery")

_store: Optional[DataStore] = None
_loaded = False


def set_store(store: Optional[DataStore]) -> None:
    """Used by tests to inject data."""
    global _store, _loaded
    _store, _loaded = store, True


def get_store() -> Optional[DataStore]:
    global _store, _loaded
    if not _loaded:
        _store = load_store(config.DATA_DIR) or load_store(config.SAMPLE_DIR, is_sample=True)
        _loaded = True
    return _store


def require_store() -> DataStore:
    store = get_store()
    if store is None:
        raise HTTPException(503, "No data loaded. Run `python scripts/ingest.py` first (see README).")
    return store


def _period(store: DataStore, start: Optional[date], end: Optional[date]):
    days = store.delivery_days()
    if not days:
        raise HTTPException(503, "Dataset contains no complete delivery days.")
    start, end = start or days[0], end or days[-1]
    if start > end:
        raise HTTPException(400, "`start` must be on or before `end`.")
    return start, end


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    store = get_store()
    if store is None:
        return {"ready": False, "message": "No data loaded. Run `python scripts/ingest.py` (see README)."}
    days = store.delivery_days()
    return {
        "ready": bool(days),
        "is_sample": store.is_sample,
        "timezone": "Europe/London",
        "delivery_days": [d.isoformat() for d in days],
        "default_cutoff": config.DEFAULT_CUTOFF,
        "cutoff_options": config.CUTOFF_OPTIONS,
        "source": store.meta,
    }


@app.get("/api/forecast")
def forecast(day: date, cutoff: str = CUTOFF):
    """The forecast a buyer can see at `cutoff` on D-1, for each half-hour of delivery day D."""
    store = require_store()
    if day not in store.delivery_days():
        raise HTTPException(404, f"No data for delivery day {day}.")
    cut = tu.cutoff_utc(day, cutoff)
    slots = analysis.day_slots(store, day, cutoff)
    band = analysis.typical_band(store, day, cutoff)

    rows = []
    for s in slots:
        row = {
            "start": tu.iso(s.start),
            "local": tu.local_hhmm(s.start),
            "forecast_mw": s.forecast,
            "published": tu.iso(s.published) if s.published else None,
            "age_h": round((cut - s.published).total_seconds() / 3600, 1) if s.published else None,
            "actual_mw": s.actual,
            "error_mw": round(s.forecast - s.actual, 1) if s.forecast is not None and s.actual is not None else None,
            "band_lo_mw": None,
            "band_hi_mw": None,
        }
        if band and s.forecast is not None:
            row["band_lo_mw"] = round(max(0.0, s.forecast + band["lo_mw"]), 1)
            row["band_hi_mw"] = round(s.forecast + band["hi_mw"], 1)
        rows.append(row)

    have = [s for s in slots if s.forecast is not None]
    summary = {"missing_slots": len(slots) - len(have), "band": band}
    if have:
        peak = max(have, key=lambda s: s.forecast)
        low = min(have, key=lambda s: s.forecast)
        summary.update({
            "forecast_gwh": round(sum(s.forecast for s in have) * 0.5 / 1000, 1),
            "peak_mw": peak.forecast, "peak_at": tu.local_hhmm(peak.start),
            "min_mw": low.forecast, "min_at": tu.local_hhmm(low.start),
            "published_min": tu.iso(min(s.published for s in have)),
            "published_max": tu.iso(max(s.published for s in have)),
        })
    with_actual = [s for s in have if s.actual is not None]
    if with_actual:
        summary["actual_gwh"] = round(sum(s.actual for s in with_actual) * 0.5 / 1000, 1)
        summary["forecast_gwh_matched"] = round(sum(s.forecast for s in with_actual) * 0.5 / 1000, 1)
    return {
        "day": day.isoformat(),
        "cutoff_local": f"{(day.fromordinal(day.toordinal() - 1)).isoformat()} {cutoff}",
        "cutoff_utc": tu.iso(cut),
        "slots": rows,
        "summary": summary,
    }


@app.get("/api/accuracy")
def accuracy(start: Optional[date] = None, end: Optional[date] = None, cutoff: str = CUTOFF):
    store = require_store()
    start, end = _period(store, start, end)
    return analysis.accuracy(store, start, end, cutoff)


@app.get("/api/horizon")
def horizon(start: Optional[date] = None, end: Optional[date] = None, cutoff: str = CUTOFF):
    store = require_store()
    start, end = _period(store, start, end)
    return analysis.horizon_analysis(store, start, end, cutoff)
