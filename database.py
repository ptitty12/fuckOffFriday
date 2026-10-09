"""SQLite storage for the fuck-off-friday meter.

Tables
------
grabs            One row per pull from Google Trends (when, from where, last date).
grab_values      The raw numbers of every grab, per company and date. Nothing is
                 ever overwritten here: this is the baseline archive.
daily_scores     The settled reading for each date: computed from the most recent
                 grab in which that date was a *complete* day.
partial_readings The reading of the grab's last (partial) date, one per grab.
                 Paired with daily_scores later, these teach us how much of a
                 day is visible at a given hour.
runs             Updater run log.

The three tables from the first version (productivity, t_series, snapshots) are
left untouched; t_series and allHistoricals.csv are imported once as "legacy"
grabs so the history chart reaches back to 2024.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional

import config
from scoring import PartialSample, local_hour, read_all_days, grab_last_date

SCHEMA = """
CREATE TABLE IF NOT EXISTS grabs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at TEXT NOT NULL,
    source TEXT NOT NULL,
    last_date TEXT,
    n_companies INTEGER,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_grabs_fetched ON grabs(fetched_at);

CREATE TABLE IF NOT EXISTS grab_values (
    grab_id INTEGER NOT NULL REFERENCES grabs(id),
    company TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (grab_id, company, date)
);
CREATE INDEX IF NOT EXISTS idx_grab_values_date ON grab_values(date);

CREATE TABLE IF NOT EXISTS daily_scores (
    date TEXT PRIMARY KEY,
    ratio REAL,
    score REAL,
    value REAL,
    grab_id INTEGER NOT NULL REFERENCES grabs(id),
    n_companies INTEGER,
    companies TEXT,
    computed_at TEXT
);

CREATE TABLE IF NOT EXISTS partial_readings (
    grab_id INTEGER PRIMARY KEY REFERENCES grabs(id),
    date TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    ratio REAL,
    value REAL,
    companies TEXT
);
CREATE INDEX IF NOT EXISTS idx_partial_date ON partial_readings(date);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    ok INTEGER,
    grab_id INTEGER,
    error TEXT
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_ts(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Optional[str] = None, import_legacy: bool = True) -> None:
    """Create tables and, the first time, import the old data as legacy grabs."""
    path = db_path or config.DB_PATH
    bundled = config.SEED_DB
    if not os.path.exists(path) and os.path.abspath(path) != os.path.abspath(bundled) and os.path.exists(bundled):
        # Fresh volume: start from the history that ships with the repo.
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        shutil.copy(bundled, path)
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        if import_legacy:
            _import_legacy(conn)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Writing grabs
# --------------------------------------------------------------------------- #

def ingest_grab(grab: Mapping[str, Mapping[str, float]], fetched_at: datetime,
                source: str = "dataforseo", note: str = "",
                conn: Optional[sqlite3.Connection] = None) -> int:
    """Store a grab verbatim, then refresh the derived tables.

    ``grab`` is ``{company: {iso_date: value}}``. Returns the new grab id.
    """
    own = conn is None
    conn = conn or connect()
    try:
        last = grab_last_date(grab)
        cur = conn.execute(
            "INSERT INTO grabs (fetched_at, source, last_date, n_companies, note) VALUES (?,?,?,?,?)",
            (iso(fetched_at), source, last, len(grab), note),
        )
        grab_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO grab_values (grab_id, company, date, value) VALUES (?,?,?,?)",
            [(grab_id, c, d, v) for c, series in grab.items() for d, v in series.items()],
        )
        _derive(conn, grab_id, grab, fetched_at)
        conn.commit()
        return grab_id
    finally:
        if own:
            conn.close()


def _derive(conn: sqlite3.Connection, grab_id: int, grab: Mapping, fetched_at: datetime) -> None:
    readings = read_all_days(grab)
    now = iso(utcnow())
    fetched_iso = iso(fetched_at)
    for r in readings:
        if r.partial:
            conn.execute(
                "INSERT OR REPLACE INTO partial_readings (grab_id, date, fetched_at, ratio, value, companies) VALUES (?,?,?,?,?,?)",
                (grab_id, r.date, fetched_iso, r.ratio, r.value, json.dumps(r.companies)),
            )
            continue
        if r.ratio is None:
            continue
        # Only a newer grab may overwrite a date's settled reading.
        existing = conn.execute(
            "SELECT g.fetched_at FROM daily_scores s JOIN grabs g ON g.id = s.grab_id WHERE s.date = ?",
            (r.date,),
        ).fetchone()
        if existing and existing["fetched_at"] > fetched_iso:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO daily_scores (date, ratio, score, value, grab_id, n_companies, companies, computed_at) VALUES (?,?,?,?,?,?,?,?)",
            (r.date, r.ratio, r.score, r.value, grab_id, r.n_companies, json.dumps(r.companies), now),
        )


def rebuild_derived(db_path: Optional[str] = None) -> None:
    """Recompute daily_scores and partial_readings from the raw archive."""
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM daily_scores")
        conn.execute("DELETE FROM partial_readings")
        for g in conn.execute("SELECT id, fetched_at FROM grabs ORDER BY fetched_at, id"):
            grab = load_grab(g["id"], conn)
            _derive(conn, g["id"], grab, parse_ts(g["fetched_at"]))
        conn.commit()
    finally:
        conn.close()


def load_grab(grab_id: int, conn: sqlite3.Connection) -> dict:
    grab: dict[str, dict[str, float]] = {}
    for row in conn.execute("SELECT company, date, value FROM grab_values WHERE grab_id = ?", (grab_id,)):
        grab.setdefault(row["company"], {})[row["date"]] = row["value"]
    return grab


# --------------------------------------------------------------------------- #
# Run log
# --------------------------------------------------------------------------- #

def start_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute("INSERT INTO runs (started_at) VALUES (?)", (iso(utcnow()),))
    conn.commit()
    return cur.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, ok: bool, grab_id: Optional[int] = None, error: str = "") -> None:
    conn.execute(
        "UPDATE runs SET finished_at = ?, ok = ?, grab_id = ?, error = ? WHERE id = ?",
        (iso(utcnow()), 1 if ok else 0, grab_id, error[:2000] if error else None, run_id),
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

def latest_grab(conn: sqlite3.Connection, source_prefix: str = "") -> Optional[sqlite3.Row]:
    if source_prefix:
        return conn.execute(
            "SELECT * FROM grabs WHERE source LIKE ? ORDER BY fetched_at DESC, id DESC LIMIT 1",
            (source_prefix + "%",),
        ).fetchone()
    return conn.execute("SELECT * FROM grabs ORDER BY fetched_at DESC, id DESC LIMIT 1").fetchone()


def latest_partial(conn: sqlite3.Connection) -> Optional[dict]:
    row = conn.execute(
        """SELECT p.*, g.source, g.n_companies FROM partial_readings p
           JOIN grabs g ON g.id = p.grab_id
           ORDER BY p.fetched_at DESC, p.grab_id DESC LIMIT 1"""
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["companies"] = json.loads(d["companies"] or "{}")
    return d


def partials_for_date(conn: sqlite3.Connection, date: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM partial_readings WHERE date = ? ORDER BY fetched_at", (date,)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["companies"] = json.loads(d["companies"] or "{}")
        out.append(d)
    return out


def calibration_samples(conn: sqlite3.Connection) -> list[PartialSample]:
    """Every past partial reading whose day has since settled."""
    rows = conn.execute(
        """SELECT p.date, p.fetched_at, p.ratio AS partial_ratio, s.ratio AS settled_ratio
           FROM partial_readings p
           JOIN daily_scores s ON s.date = p.date
           JOIN grabs g ON g.id = p.grab_id
           WHERE p.ratio IS NOT NULL AND s.ratio IS NOT NULL
             AND g.source NOT LIKE 'legacy%'"""
    ).fetchall()
    out = []
    for r in rows:
        out.append(PartialSample(
            date=r["date"],
            local_hour=local_hour(parse_ts(r["fetched_at"]), config.TZ),
            partial_ratio=r["partial_ratio"],
            settled_ratio=r["settled_ratio"],
        ))
    return out


def daily_scores(conn: sqlite3.Connection, since: Optional[str] = None, until: Optional[str] = None) -> list[dict]:
    q = "SELECT date, ratio, score, value, grab_id, n_companies, companies FROM daily_scores"
    conds, args = [], []
    if since:
        conds.append("date >= ?"); args.append(since)
    if until:
        conds.append("date <= ?"); args.append(until)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY date"
    out = []
    for r in conn.execute(q, args):
        d = dict(r)
        d["companies"] = json.loads(d["companies"] or "{}")
        out.append(d)
    return out


def status(conn: sqlite3.Connection) -> dict:
    g = conn.execute("SELECT COUNT(*) AS n, MIN(fetched_at) AS first, MAX(fetched_at) AS last FROM grabs WHERE source NOT LIKE 'legacy%'").fetchone()
    s = conn.execute("SELECT COUNT(*) AS n, MIN(date) AS first, MAX(date) AS last FROM daily_scores").fetchone()
    p = conn.execute("SELECT COUNT(*) AS n FROM partial_readings").fetchone()
    last_run = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    return {
        "grabs": {"n": g["n"], "first": g["first"], "last": g["last"]},
        "settled_days": {"n": s["n"], "first": s["first"], "last": s["last"]},
        "partial_readings": p["n"],
        "last_run": dict(last_run) if last_run else None,
    }


def calibration_coverage(conn: sqlite3.Connection) -> list[dict]:
    """How many settled partial samples exist per local hour band and weekday."""
    samples = calibration_samples(conn)
    buckets: dict[tuple, int] = {}
    for s in samples:
        band = int(s.local_hour // 3) * 3
        wd = datetime.fromisoformat(s.date).weekday()
        buckets[(band, wd)] = buckets.get((band, wd), 0) + 1
    return [
        {"hour_band": f"{b:02d}:00-{b + 3:02d}:00", "weekday": wd, "n": n}
        for (b, wd), n in sorted(buckets.items())
    ]


# --------------------------------------------------------------------------- #
# Legacy import
# --------------------------------------------------------------------------- #

def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _import_legacy(conn: sqlite3.Connection) -> None:
    # v1 t_series: the 3-company average, Dec 2024 - May 2025.
    if _table_exists(conn, "t_series") and not conn.execute(
            "SELECT 1 FROM grabs WHERE source = 'legacy_t_series'").fetchone():
        rows = conn.execute("SELECT date, value FROM t_series WHERE value IS NOT NULL ORDER BY date").fetchall()
        if rows:
            series = {r["date"]: float(r["value"]) for r in rows}
            # The v1 updater last ran 2025-05-05 20:56 local; use that as the fetch time.
            fetched = datetime(2025, 5, 6, 1, 56, tzinfo=timezone.utc)
            ingest_grab({"average": series}, fetched, source="legacy_t_series",
                        note="imported from v1 t_series table", conn=conn)

    # allHistoricals.csv: calendar 2024, five companies, keep the ones we track.
    if os.path.exists(config.LEGACY_CSV) and not conn.execute(
            "SELECT 1 FROM grabs WHERE source = 'legacy_csv'").fetchone():
        grab: dict[str, dict[str, float]] = {}
        with open(config.LEGACY_CSV, newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    d = datetime.strptime(row["date"], "%m/%d/%Y").date().isoformat()
                except (KeyError, ValueError):
                    continue
                for c in config.COMPANIES:
                    v = row.get(c)
                    if v not in (None, ""):
                        grab.setdefault(c, {})[d] = float(v)
        if grab:
            last = grab_last_date(grab)
            fetched = datetime.fromisoformat(last).replace(hour=23, minute=59, tzinfo=timezone.utc)
            ingest_grab(grab, fetched, source="legacy_csv", note="imported from allHistoricals.csv", conn=conn)
