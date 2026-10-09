"""Assemble what the site shows from what the database holds."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import config
import database as db
from scoring import (WEEKDAY_NAMES, apply_calibration, calibrate, local_hour,
                     mood_for, parse_date, weekday_profile)


def _pct(ratio: Optional[float]) -> Optional[float]:
    return None if ratio is None else round((ratio - 1.0) * 100.0, 1)


def _label_for(date_str: str, today) -> str:
    d = parse_date(date_str)
    delta = (today - d).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    return d.strftime("%a %b %-d")


def _local(ts: str) -> datetime:
    return db.parse_ts(ts).astimezone(config.TZ)


def today_payload(conn: sqlite3.Connection) -> dict:
    now_local = datetime.now(config.TZ)
    today = now_local.date()
    partial = db.latest_partial(conn)
    if partial and str(partial.get("source", "")).startswith("legacy"):
        partial = None  # imported history has no live reading to show
    samples = db.calibration_samples(conn)

    settled_rows = db.daily_scores(conn)
    settled_rows = [r for r in settled_rows if r["score"] is not None]

    reading = None
    intraday = []
    if partial:
        fetched_local = _local(partial["fetched_at"])
        hour = local_hour(db.parse_ts(partial["fetched_at"]), config.TZ)
        cal = calibrate(partial["date"], hour, samples)
        cal_ratio = apply_calibration(partial["ratio"], cal)
        companies = {}
        for name, r in (partial["companies"] or {}).items():
            companies[name] = {
                "raw": _pct(r),
                "score": _pct(r / cal.factor) if cal.calibrated else None,
            }
        reading = {
            "date": partial["date"],
            "weekday": WEEKDAY_NAMES[parse_date(partial["date"]).weekday()],
            "label": _label_for(partial["date"], today),
            "fetched_at": partial["fetched_at"],
            "fetched_local": fetched_local.strftime("%-I:%M %p"),
            "fetched_local_full": fetched_local.strftime("%a %b %-d, %-I:%M %p %Z"),
            "local_hour": round(hour, 2),
            "raw_score": _pct(partial["ratio"]),
            "score": _pct(cal_ratio),
            "calibrated": cal.calibrated,
            "calibration": {
                "n": cal.n,
                "method": cal.method,
                "factor": round(cal.factor, 3) if cal.factor else None,
                "spread_pct": round(cal.spread * 100.0, 1) if cal.spread is not None else None,
                "needed": max(0, 3 - cal.n) if not cal.calibrated else 0,
            },
            "companies": companies,
            "mood": mood_for(_pct(cal_ratio) if cal.calibrated else None),
            "source": partial.get("source"),
        }
        for p in db.partials_for_date(conn, partial["date"]):
            h = local_hour(db.parse_ts(p["fetched_at"]), config.TZ)
            c = calibrate(p["date"], h, samples)
            intraday.append({
                "fetched_local": _local(p["fetched_at"]).strftime("%-I:%M %p"),
                "local_hour": round(h, 2),
                "raw_score": _pct(p["ratio"]),
                "score": _pct(apply_calibration(p["ratio"], c)),
            })

    settled = None
    if settled_rows:
        last = settled_rows[-1]
        if not partial or last["date"] < partial["date"]:
            settled = {
                "date": last["date"],
                "weekday": WEEKDAY_NAMES[parse_date(last["date"]).weekday()],
                "label": _label_for(last["date"], today),
                "score": round(last["score"], 1),
                "companies": {k: {"score": _pct(v)} for k, v in (last["companies"] or {}).items()},
                "mood": mood_for(last["score"]),
            }

    if reading and reading["calibrated"]:
        headline = "reading"
    elif settled:
        headline = "settled"
    else:
        headline = "reading" if reading else "none"

    return {
        "headline": headline,
        "reading": reading,
        "settled": settled,
        "intraday": intraday,
        "tz": config.TZ_NAME,
        "now_local": now_local.strftime("%a %b %-d, %-I:%M %p %Z"),
        "companies": config.COMPANIES,
    }


def history_payload(conn: sqlite3.Connection, days: Optional[int] = None) -> dict:
    rows = db.daily_scores(conn)
    rows = [r for r in rows if r["score"] is not None]
    if days and rows:
        cutoff = (parse_date(rows[-1]["date"]) - timedelta(days=days)).isoformat()
        rows = [r for r in rows if r["date"] > cutoff]
    out = [{
        "date": r["date"],
        "weekday": parse_date(r["date"]).weekday(),
        "score": round(r["score"], 1),
        "companies": {k: _pct(v) for k, v in (r["companies"] or {}).items()},
        "grab_id": r["grab_id"],
    } for r in rows]
    return {"days": out}


def profile_payload(conn: sqlite3.Connection, weeks: Optional[int] = None) -> dict:
    rows = db.daily_scores(conn)
    if weeks and rows:
        cutoff = (parse_date(rows[-1]["date"]) - timedelta(weeks=weeks)).isoformat()
        rows = [r for r in rows if r["date"] > cutoff]
    prof = weekday_profile(rows)
    return {"weekdays": prof, "n_weeks": max((p["n_weeks"] for p in prof), default=0)}


def status_payload(conn: sqlite3.Connection) -> dict:
    s = db.status(conn)
    s["calibration_coverage"] = db.calibration_coverage(conn)
    s["tz"] = config.TZ_NAME
    s["companies"] = config.COMPANIES
    s["lookback_days"] = config.LOOKBACK_DAYS
    return s


def dashboard_payload(conn: sqlite3.Connection) -> dict:
    return {
        "today": today_payload(conn),
        "history": history_payload(conn),
        "profile": profile_payload(conn),
        "status": status_payload(conn),
    }
