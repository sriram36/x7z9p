from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app import analysis, timeutil as tu
from backend.app.store import DataStore

UTC = timezone.utc
DAYS = [date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4), date(2026, 1, 5)]


def make_store() -> DataStore:
    """Actual wind is flat 1000 MW. Each delivery day D has three forecast publishes:
    early  D-2 12:00Z -> 1300 (error +300)
    mid    D-1 06:00Z -> 1100 (error +100)   <- visible at a 09:00 cutoff
    late   D-1 12:00Z -> 1000 (error   0)    <- published after a 09:00 cutoff
    """
    actuals, forecasts = {}, []
    for d in DAYS:
        mid = datetime(d.year, d.month, d.day, tzinfo=UTC)
        for t in tu.delivery_slots(d):
            actuals[t] = 1000.0
            forecasts += [
                (t, mid - timedelta(days=2) + timedelta(hours=12), 1300.0),
                (t, mid - timedelta(days=1) + timedelta(hours=6), 1100.0),
                (t, mid - timedelta(days=1) + timedelta(hours=12), 1000.0),
            ]
    return DataStore(actuals, forecasts)


def test_slots_and_dst():
    assert len(tu.delivery_slots(date(2026, 1, 8))) == 48
    assert len(tu.delivery_slots(date(2026, 3, 29))) == 46
    assert len(tu.delivery_slots(date(2026, 10, 25))) == 50


def test_cutoff_is_uk_local_time_on_previous_day():
    assert tu.cutoff_utc(date(2026, 1, 8), "09:00") == datetime(2026, 1, 7, 9, 0, tzinfo=UTC)
    assert tu.cutoff_utc(date(2026, 7, 8), "09:00") == datetime(2026, 7, 7, 8, 0, tzinfo=UTC)  # BST


@pytest.mark.parametrize("cutoff,expected", [("05:00", 1300.0), ("09:00", 1100.0), ("13:00", 1000.0)])
def test_latest_forecast_before_cutoff(cutoff, expected):
    slots = analysis.day_slots(make_store(), DAYS[1], cutoff)
    assert {s.forecast for s in slots} == {expected}


def test_forecast_published_after_cutoff_is_never_used():
    store = make_store()
    cut = tu.cutoff_utc(DAYS[1], "09:00")
    for s in analysis.day_slots(store, DAYS[1], "09:00"):
        assert s.published <= cut


def test_no_forecast_before_first_publish():
    store = make_store()
    t = tu.delivery_slots(DAYS[0])[0]
    assert store.forecast_asof(t, datetime(2020, 1, 1, tzinfo=UTC)) is None


def test_summarize_known_values():
    s = analysis.summarize([(1100, 1000), (900, 1000)])
    assert (s["mae_mw"], s["rmse_mw"], s["bias_mw"], s["over_share_pct"]) == (100.0, 100.0, 0.0, 50.0)


def test_summarize_empty():
    assert analysis.summarize([]) == {"n": 0}


def test_percentile():
    assert analysis.percentile([1, 2, 3, 4], 50) == 2.5
    assert analysis.percentile([5], 95) == 5
    assert analysis.percentile([], 50) is None


def test_accuracy_at_cutoff():
    res = analysis.accuracy(make_store(), DAYS[0], DAYS[-1], "09:00")
    assert res["overall"]["mae_mw"] == 100.0 and res["overall"]["bias_mw"] == 100.0
    assert res["period"]["days"] == 4
    assert len(res["by_hour"]) == 24
    assert res["by_level"][0]["label"].startswith("0.0")


def test_horizon_uses_all_publishes():
    res = analysis.horizon_analysis(make_store(), DAYS[0], DAYS[-1], "09:00")
    total_n = sum(b["n"] for b in res["buckets"])
    assert total_n == 3 * 48 * 4
    mean_bias = sum(b["bias_mw"] * b["n"] for b in res["buckets"]) / total_n
    assert mean_bias == pytest.approx((300 + 100 + 0) / 3, abs=1)
    assert res["decision_window_h"] == [15.0, 38.5]
    assert any(b["in_decision_window"] for b in res["buckets"])


def test_band_uses_only_earlier_days_when_enough_history():
    store = make_store()
    band = analysis.typical_band(store, DAYS[3], "09:00")
    assert band["basis"] == "previous days" and band["days"] == 3
    assert band["lo_mw"] == band["hi_mw"] == -100.0  # actual - forecast


def test_hourly_forecast_supports_half_hour_slots():
    """Real Elexon WINDFOR forecasts are published hourly (at :00). Half-hour targets (:30)
    should inherit the hourly forecast."""
    d = DAYS[0]
    mid = datetime(d.year, d.month, d.day, tzinfo=UTC)
    actuals = {t: 1000.0 for t in tu.delivery_slots(d)}
    # Hourly forecasts only
    hourly_targets = [mid + timedelta(hours=i) for i in range(24)]
    forecasts = [(t, mid - timedelta(days=1) + timedelta(hours=6), 1200.0) for t in hourly_targets]
    store = DataStore(actuals, forecasts)

    # delivery_days detects the day with 24 hourly slots
    assert store.delivery_days() == [d]

    # Both :00 and :30 half-hour slots resolve to the forecast
    t_00 = tu.delivery_slots(d)[0]
    t_30 = tu.delivery_slots(d)[1]
    cut = tu.cutoff_utc(d, "09:00")
    assert store.forecast_asof(t_00, cut)[1] == 1200.0
    assert store.forecast_asof(t_30, cut)[1] == 1200.0
    assert len(store.forecast_history(t_30)) == 1

    # day_slots populates all 48 slots without missing values
    slots = analysis.day_slots(store, d, "09:00")
    assert len(slots) == 48
    assert all(s.forecast == 1200.0 for s in slots)

