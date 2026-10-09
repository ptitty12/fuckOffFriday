from datetime import date, timedelta

from scoring import (PartialSample, apply_calibration, baseline_for, calibrate,
                     mood_for, read_all_days, read_day, weekday_profile)


def make_series(start: str, days: int, level, last_partial_fraction=1.0):
    """Synthetic series where each weekday has a fixed level, last day partial."""
    out = {}
    d0 = date.fromisoformat(start)
    for i in range(days):
        d = d0 + timedelta(days=i)
        v = level(d)
        if i == days - 1:
            v *= last_partial_fraction
        out[d.isoformat()] = v
    return out


def weekday_level(d):
    return {0: 80, 1: 85, 2: 85, 3: 82, 4: 70, 5: 30, 6: 28}[d.weekday()]


def test_baseline_uses_same_weekday_complete_days_only():
    s = make_series("2025-01-06", 29, weekday_level)  # Mon .. Mon(partial)
    last = max(s)
    assert last == "2025-02-03"
    # Target Monday: 4 earlier Mondays at 80, the partial Monday is excluded.
    assert baseline_for(s, "2025-01-20", last) == 80
    # Too few samples -> None
    assert baseline_for(s, "2025-01-20", last, min_samples=10) is None


def test_read_day_averages_company_ratios():
    a = make_series("2025-01-06", 29, weekday_level)
    b = {k: v * 2 for k, v in a.items()}  # different normalisation, same shape
    b["2025-01-20"] = 80 * 2 * 1.5          # Monday 50% up for company b
    grab = {"a": a, "b": b}
    r = read_day(grab, "2025-01-20", max(a))
    assert r.companies["a"] == 1.0
    assert abs(r.companies["b"] - 1.5) < 1e-9
    assert abs(r.score - 25.0) < 1e-9
    assert not r.partial


def test_last_day_is_partial():
    s = make_series("2025-01-06", 29, weekday_level, last_partial_fraction=0.4)
    readings = read_all_days({"x": s})
    assert readings[-1].partial
    assert abs(readings[-1].ratio - 0.4) < 1e-9
    assert all(not r.partial for r in readings[:-1])


def test_calibration_prefers_same_weekday_then_daytype():
    samples = [
        PartialSample("2025-01-06", 9.0, 0.4, 1.0),   # Mon
        PartialSample("2025-01-13", 9.2, 0.42, 1.0),  # Mon
        PartialSample("2025-01-20", 8.9, 0.38, 1.0),  # Mon
        PartialSample("2025-01-07", 9.0, 0.5, 1.0),   # Tue
        PartialSample("2025-01-08", 9.0, 0.5, 1.0),   # Wed
        PartialSample("2025-01-09", 14.0, 0.8, 1.0),  # Thu, wrong hour
    ]
    cal = calibrate("2025-01-27", 9.0, samples)  # a Monday
    assert cal.method == "same_weekday"
    assert cal.n == 3
    assert abs(cal.factor - 0.4) < 1e-9

    cal = calibrate("2025-01-28", 9.0, samples)  # a Tuesday: 5 weekday samples at 9am
    assert cal.method == "same_daytype"
    assert cal.n == 5

    cal = calibrate("2025-02-01", 9.0, samples)  # a Saturday: nothing comparable
    assert cal.method == "none"
    assert not cal.calibrated

    cal = calibrate("2025-01-28", 14.0, samples)  # 2pm: only the Thu sample fits
    assert not cal.calibrated
    assert cal.n == 1


def test_calibration_recovers_true_score():
    samples = [PartialSample(f"2025-01-{d:02d}", 9.0, 0.35 * r, r) for d, r in ((6, 1.0), (7, 0.9), (8, 1.1))]
    cal = calibrate("2025-01-09", 9.0, samples)
    assert cal.calibrated
    # Today reads 0.28 partial; true ratio is 0.8 (-20%)
    assert abs(apply_calibration(0.28, cal) - 0.8) < 1e-9


def test_calibration_picks_closest_hour_per_date():
    samples = [
        PartialSample("2025-01-06", 8.0, 0.3, 1.0),
        PartialSample("2025-01-06", 9.9, 0.5, 1.0),  # closer to 10:00
        PartialSample("2025-01-07", 10.0, 0.5, 1.0),
        PartialSample("2025-01-08", 10.0, 0.5, 1.0),
    ]
    cal = calibrate("2025-01-09", 10.0, samples)
    assert cal.n == 3
    assert abs(cal.factor - 0.5) < 1e-9


def test_weekday_profile_relative_to_working_week():
    rows = []
    d0 = date(2025, 1, 6)
    for i in range(21):
        d = d0 + timedelta(days=i)
        rows.append({"date": d.isoformat(), "value": weekday_level(d), "grab_id": 1})
    prof = weekday_profile(rows)
    mean_work = (80 + 85 + 85 + 82 + 70) / 5
    fri = next(p for p in prof if p["name"] == "Friday")
    assert fri["n_weeks"] == 3
    assert abs(fri["level_pct"] - round((70 / mean_work - 1) * 100, 1)) < 0.05
    sat = next(p for p in prof if p["name"] == "Saturday")
    assert sat["level_pct"] < -50


def test_weekday_profile_ignores_weeks_spanning_grabs():
    rows = []
    d0 = date(2025, 1, 6)
    for i in range(7):
        d = d0 + timedelta(days=i)
        rows.append({"date": d.isoformat(), "value": weekday_level(d), "grab_id": 1 if i < 3 else 2})
    prof = weekday_profile(rows)
    assert all(p["n_weeks"] == 0 for p in prof)


def test_moods():
    assert mood_for(None)["label"] == "No reading yet"
    assert mood_for(15)["emoji"] == "🤖"
    assert mood_for(0)["label"].startswith("Just another")
    assert mood_for(-25)["label"] == "Full fuck-off mode"
