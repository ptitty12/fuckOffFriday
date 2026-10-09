"""Pure scoring logic for the fuck-off-friday meter.

Everything in here works on plain Python data so it is easy to test.

Vocabulary
----------
grab        One pull of Google Trends data: ``{company: {date: value}}``.
            Google normalises every pull to its own 0-100 scale, so values from
            different grabs are never compared directly. All maths happens
            *within* a grab, and only scale-free ratios leave it.
baseline    For a given date inside a grab, the median value of the same
            weekday over the *complete* days of that grab (the date itself is
            excluded). "Complete" means strictly before the grab's last date;
            the last date of a grab is always treated as partial, because
            Google reports the current day with only the hours seen so far.
ratio       value / baseline. 1.0 means "a perfectly normal Tuesday".
score       (ratio - 1) * 100, a percentage. Negative means people are not
            searching for their work tools, i.e. they are fucking off.
calibration The partial-day problem: a grab taken at 9am only contains a
            third of the day, so today's ratio reads low. Once we have seen
            how earlier same-hour partial readings compared to the settled
            value of those days, we can divide today's partial ratio by the
            typical completion factor and get an honest estimate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type, datetime, timedelta
from statistics import median
from typing import Iterable, Mapping, Optional, Sequence

MIN_BASELINE_SAMPLES = 3
MIN_CALIBRATION_SAMPLES = 3
HOUR_TOLERANCE = 1.5  # hours either side when matching grabs by time of day
FACTOR_BOUNDS = (0.05, 1.5)  # ignore completion factors outside this range

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def parse_date(value: str | date_type | datetime) -> date_type:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date_type):
        return value
    return date_type.fromisoformat(str(value)[:10])


# --------------------------------------------------------------------------- #
# Within-grab maths
# --------------------------------------------------------------------------- #

def baseline_for(series: Mapping[str, float], target: str, last_date: str,
                 min_samples: int = MIN_BASELINE_SAMPLES) -> Optional[float]:
    """Median of the same weekday among complete days of ``series``.

    ``series`` maps ISO date -> value for one company within one grab.
    ``last_date`` is the grab's last date (treated as partial, never used).
    Returns None when fewer than ``min_samples`` comparable days exist or the
    median is zero.
    """
    tgt = parse_date(target)
    wd = tgt.weekday()
    samples = []
    for d, v in series.items():
        if d == target or d >= last_date or v is None:
            continue
        if parse_date(d).weekday() == wd:
            samples.append(float(v))
    if len(samples) < min_samples:
        return None
    base = median(samples)
    if base <= 0:
        return None
    return base


def company_ratio(series: Mapping[str, float], target: str, last_date: str) -> Optional[float]:
    value = series.get(target)
    if value is None:
        return None
    base = baseline_for(series, target, last_date)
    if base is None:
        return None
    return float(value) / base


@dataclass
class DayReading:
    date: str
    ratio: Optional[float]           # mean ratio across companies, None if unscorable
    companies: dict = field(default_factory=dict)  # company -> ratio
    value: Optional[float] = None    # mean raw value across companies (within-grab scale)
    partial: bool = False
    n_companies: int = 0

    @property
    def score(self) -> Optional[float]:
        return None if self.ratio is None else (self.ratio - 1.0) * 100.0


def read_day(grab: Mapping[str, Mapping[str, float]], target: str, last_date: str) -> DayReading:
    """Score one date inside a grab, averaging the per-company ratios."""
    ratios = {}
    values = []
    for company, series in grab.items():
        v = series.get(target)
        if v is not None:
            values.append(float(v))
        r = company_ratio(series, target, last_date)
        if r is not None:
            ratios[company] = r
    mean_ratio = sum(ratios.values()) / len(ratios) if ratios else None
    mean_value = sum(values) / len(values) if values else None
    return DayReading(
        date=target,
        ratio=mean_ratio,
        companies=ratios,
        value=mean_value,
        partial=(target >= last_date),
        n_companies=len(ratios),
    )


def grab_last_date(grab: Mapping[str, Mapping[str, float]]) -> Optional[str]:
    dates = [d for series in grab.values() for d in series.keys()]
    return max(dates) if dates else None


def read_all_days(grab: Mapping[str, Mapping[str, float]]) -> list[DayReading]:
    """Score every date of a grab. The last date comes back flagged partial."""
    last = grab_last_date(grab)
    if last is None:
        return []
    dates = sorted({d for series in grab.values() for d in series.keys()})
    return [read_day(grab, d, last) for d in dates]


# --------------------------------------------------------------------------- #
# Partial-day calibration
# --------------------------------------------------------------------------- #

@dataclass
class PartialSample:
    """A past same-hour partial reading, paired with how the day settled."""
    date: str
    local_hour: float
    partial_ratio: float
    settled_ratio: float

    @property
    def factor(self) -> float:
        return self.partial_ratio / self.settled_ratio


@dataclass
class Calibration:
    factor: Optional[float]
    n: int
    method: str                 # "same_weekday", "same_daytype", "none"
    spread: Optional[float]     # median absolute deviation of the factors, as a ratio
    samples: list = field(default_factory=list)

    @property
    def calibrated(self) -> bool:
        return self.factor is not None


def hour_distance(a: float, b: float) -> float:
    d = abs(a - b) % 24.0
    return min(d, 24.0 - d)


def is_weekend(d: str | date_type) -> bool:
    return parse_date(d).weekday() >= 5


def calibrate(target_date: str, target_hour: float, samples: Iterable[PartialSample],
              tolerance: float = HOUR_TOLERANCE,
              min_samples: int = MIN_CALIBRATION_SAMPLES) -> Calibration:
    """Pick the completion factor to apply to a partial reading taken at
    ``target_hour`` on ``target_date``.

    Preference order: same weekday at the same hour; then any day of the same
    type (weekday vs weekend) at the same hour. Within a date, only the sample
    closest in time is used, so grabbing several times a day does not let one
    day dominate.
    """
    tgt_wd = parse_date(target_date).weekday()
    tgt_weekend = tgt_wd >= 5

    # Keep the best sample per date within the time tolerance.
    best: dict[str, PartialSample] = {}
    for s in samples:
        if s.date == target_date or s.settled_ratio <= 0 or s.partial_ratio <= 0:
            continue
        dist = hour_distance(s.local_hour, target_hour)
        if dist > tolerance:
            continue
        if not (FACTOR_BOUNDS[0] <= s.factor <= FACTOR_BOUNDS[1]):
            continue
        prev = best.get(s.date)
        if prev is None or dist < hour_distance(prev.local_hour, target_hour):
            best[s.date] = s

    usable = list(best.values())
    same_wd = [s for s in usable if parse_date(s.date).weekday() == tgt_wd]
    same_type = [s for s in usable if is_weekend(s.date) == tgt_weekend]

    if len(same_wd) >= min_samples:
        chosen, method = same_wd, "same_weekday"
    elif len(same_type) >= min_samples:
        chosen, method = same_type, "same_daytype"
    else:
        return Calibration(factor=None, n=len(same_type), method="none", spread=None, samples=same_type)

    factors = [s.factor for s in chosen]
    f = median(factors)
    spread = median([abs(x - f) for x in factors]) / f if f else None
    return Calibration(factor=f, n=len(chosen), method=method, spread=spread, samples=chosen)


def apply_calibration(partial_ratio: Optional[float], cal: Calibration) -> Optional[float]:
    if partial_ratio is None or not cal.calibrated:
        return None
    return partial_ratio / cal.factor


# --------------------------------------------------------------------------- #
# Weekday profile ("which day do people actually fuck off?")
# --------------------------------------------------------------------------- #

def weekday_profile(rows: Sequence[Mapping]) -> list[dict]:
    """Typical level of each weekday relative to that week's Mon-Fri mean.

    ``rows`` are settled daily readings with keys ``date``, ``value`` and
    ``grab_id``. A week only counts when all five working days come from the
    same grab (same normalisation). Weekends are reported relative to the
    working-day mean of their own week, which is where the comedy lives.
    """
    by_week: dict[tuple, dict[int, Mapping]] = {}
    for r in rows:
        if r.get("value") is None:
            continue
        d = parse_date(r["date"])
        iso = d.isocalendar()
        by_week.setdefault((iso[0], iso[1]), {})[d.weekday()] = r

    levels: dict[int, list[float]] = {i: [] for i in range(7)}
    weeks_used = 0
    for _, days in by_week.items():
        work = [days[i] for i in range(5) if i in days]
        if len(work) < 5:
            continue
        if len({w["grab_id"] for w in work}) != 1:
            continue
        mean_work = sum(float(w["value"]) for w in work) / 5.0
        if mean_work <= 0:
            continue
        weeks_used += 1
        for i, r in days.items():
            if r["grab_id"] != work[0]["grab_id"]:
                continue
            levels[i].append(float(r["value"]) / mean_work - 1.0)

    out = []
    for i in range(7):
        vals = levels[i]
        out.append({
            "weekday": i,
            "name": WEEKDAY_NAMES[i],
            "level_pct": round(median(vals) * 100.0, 1) if vals else None,
            "n_weeks": len(vals),
        })
    return out


# --------------------------------------------------------------------------- #
# Mood
# --------------------------------------------------------------------------- #

MOODS = [
    (10.0, "🤖", "Suspiciously productive"),
    (3.0, "💪", "Locked in"),
    (-3.0, "😐", "Just another day at the office"),
    (-10.0, "☕", "Coasting"),
    (-20.0, "🏖️", "Half-day energy"),
    (float("-inf"), "🍻", "Full fuck-off mode"),
]


def mood_for(score: Optional[float]) -> dict:
    if score is None:
        return {"emoji": "🤷", "label": "No reading yet"}
    for threshold, emoji, label in MOODS:
        if score >= threshold:
            return {"emoji": emoji, "label": label}
    return {"emoji": "🍻", "label": "Full fuck-off mode"}


def local_hour(fetched_at_utc: datetime, tz) -> float:
    local = fetched_at_utc.astimezone(tz)
    return local.hour + local.minute / 60.0


def days_between(a: str, b: str) -> int:
    return (parse_date(b) - parse_date(a)).days


def shift_date(d: str, days: int) -> str:
    return (parse_date(d) + timedelta(days=days)).isoformat()
