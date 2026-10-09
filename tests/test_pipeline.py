"""End-to-end: fake Google Trends -> updater -> database -> API payloads."""
import os
from datetime import date, datetime, timedelta, timezone

import pytest

import config
import database as db
import meter
from scoring import parse_date
from update_db import run_update

LEVEL = {0: 80, 1: 85, 2: 85, 3: 82, 4: 70, 5: 30, 6: 28}


class FakeTrends:
    """Deterministic 'Google': true daily level per weekday, with a special
    bad day, reported as a fraction of the day at the hour of the grab."""

    def __init__(self, bad_day: str, bad_factor: float):
        self.bad_day = bad_day
        self.bad_factor = bad_factor
        self.now = datetime(2025, 3, 3, 15, 0, tzinfo=timezone.utc)  # 9am Chicago (CST)

    def true_value(self, company: str, d: date) -> float:
        scale = {"Salesforce": 1.0, "Oracle": 0.7, "Workday": 0.5}[company]
        v = LEVEL[d.weekday()] * scale
        if d.isoformat() == self.bad_day:
            v *= self.bad_factor
        return v

    def fraction_seen(self) -> float:
        local = self.now.astimezone(config.TZ)
        h = local.hour + local.minute / 60
        return min(1.0, max(0.05, h / 24.0))

    def __call__(self, company, date_from, date_to):
        out = {}
        d = parse_date(date_from)
        end = self.now.astimezone(config.TZ).date()
        while d <= end:
            v = self.true_value(company, d)
            if d == end:
                v *= self.fraction_seen()
            out[d.isoformat()] = v
            d += timedelta(days=1)
        # Google rescales every pull so the max is 100
        m = max(out.values())
        return {k: v / m * 100 for k, v in out.items()}


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "LEGACY_CSV", str(tmp_path / "nope.csv"))
    monkeypatch.setattr(config, "SEED_DB", str(tmp_path / "nope.db"))
    monkeypatch.setattr(config, "LOG_PATH", str(tmp_path / "log"))
    db.init_db()
    return path


def grab_at(fake, monkeypatch, when: datetime):
    fake.now = when
    monkeypatch.setattr(db, "utcnow", lambda: when)
    import trends
    real_fetch_grab = trends.fetch_grab

    def patched(companies=None, lookback_days=None, fetcher=None):
        # trends.fetch_grab uses the real clock for the date window; pin it.
        today = when.astimezone(config.TZ).date()
        date_from = (today - timedelta(days=config.LOOKBACK_DAYS)).isoformat()
        grab = {c: fake(c, date_from, today.isoformat()) for c in config.COMPANIES}
        return grab, []

    monkeypatch.setattr(trends, "fetch_grab", patched)
    gid = run_update()
    assert gid is not None
    return gid


def test_calibration_fixes_partial_day_reading(fresh_db, monkeypatch):
    bad_day = "2025-03-13"  # a Thursday that is 25% down
    fake = FakeTrends(bad_day, 0.75)

    # Four weekday grabs at 9am local before the bad day -> calibration samples.
    start = datetime(2025, 3, 3, 15, 0, tzinfo=timezone.utc)  # Mon 9am CST
    for i in range(9):  # Mon 3 .. Tue 11 (skipping nothing; weekends included)
        grab_at(fake, monkeypatch, start + timedelta(days=i))

    conn = db.connect()
    st = meter.status_payload(conn)
    assert st["grabs"]["n"] == 9
    # Partial readings for days 3..10 are now settled by later grabs.
    assert len(db.calibration_samples(conn)) == 8
    conn.close()

    # Now the bad Thursday, grabbed at 9am local (DST started Mar 9 -> 14:00 UTC).
    grab_at(fake, monkeypatch, datetime(2025, 3, 13, 14, 0, tzinfo=timezone.utc))
    conn = db.connect()
    t = meter.today_payload(conn)
    conn.close()

    r = t["reading"]
    assert r["date"] == bad_day
    assert r["label"] != "Today"  # test clock is not the real clock
    assert r["calibrated"]
    assert r["calibration"]["method"] == "same_daytype"  # only one earlier Thursday
    # Raw reading is wildly low (only 9/24 of the day seen); calibrated is honest.
    assert r["raw_score"] < -60
    assert abs(r["score"] - (-25.0)) < 1.0
    assert t["headline"] == "reading"
    assert r["mood"]["label"] == "Full fuck-off mode"
    for c in config.COMPANIES:
        assert abs(r["companies"][c]["score"] - (-25.0)) < 1.0

    # Next morning the bad day settles at -25% too.
    grab_at(fake, monkeypatch, datetime(2025, 3, 14, 14, 0, tzinfo=timezone.utc))
    conn = db.connect()
    h = meter.history_payload(conn)
    conn.close()
    settled = next(d for d in h["days"] if d["date"] == bad_day)
    assert abs(settled["score"] - (-25.0)) < 0.5
    assert all(abs(d["score"]) < 0.5 for d in h["days"] if d["date"] != bad_day)


def test_uncalibrated_falls_back_to_settled_day(fresh_db, monkeypatch):
    fake = FakeTrends("2099-01-01", 1.0)
    grab_at(fake, monkeypatch, datetime(2025, 3, 3, 15, 0, tzinfo=timezone.utc))
    conn = db.connect()
    t = meter.today_payload(conn)
    conn.close()
    assert t["reading"]["calibrated"] is False
    assert t["reading"]["calibration"]["needed"] == 3
    assert t["headline"] == "settled"
    assert t["settled"]["date"] == "2025-03-02"


def test_rebuild_is_idempotent(fresh_db, monkeypatch):
    fake = FakeTrends("2025-03-05", 0.5)
    for i in range(4):
        grab_at(fake, monkeypatch, datetime(2025, 3, 3 + i, 15, 0, tzinfo=timezone.utc))
    conn = db.connect()
    before = meter.history_payload(conn)
    conn.close()
    db.rebuild_derived()
    conn = db.connect()
    after = meter.history_payload(conn)
    conn.close()
    assert before == after


def test_legacy_import_from_real_repo_db(tmp_path, monkeypatch):
    import shutil
    src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "productivity.db")
    if not os.path.exists(src):
        pytest.skip("no repo db")
    path = str(tmp_path / "legacy.db")
    shutil.copy(src, path)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    conn = db.connect()
    st = meter.status_payload(conn)
    assert st["settled_days"]["n"] > 400
    assert st["grabs"]["n"] == 0  # legacy grabs do not count as live grabs
    assert db.calibration_samples(conn) == []  # and never calibrate anything
    prof = meter.profile_payload(conn)
    fri = next(p for p in prof["weekdays"] if p["name"] == "Friday")
    assert fri["level_pct"] < 0  # fuck off friday, confirmed by data
    t = meter.today_payload(conn)
    assert t["reading"] is None and t["headline"] == "settled"
    conn.close()
