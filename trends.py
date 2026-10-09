"""Pull daily Google Trends interest from DataForSEO."""
from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

import requests

import config

log = logging.getLogger(__name__)

URL = "https://api.dataforseo.com/v3/keywords_data/google_trends/explore/live"
LOCATION_US = 2840


class TrendsError(RuntimeError):
    pass


def auth_header() -> str:
    if config.DATAFORSEO_AUTH:
        a = config.DATAFORSEO_AUTH
        return a if a.lower().startswith("basic ") else f"Basic {a}"
    if config.DATAFORSEO_LOGIN and config.DATAFORSEO_PASSWORD:
        token = base64.b64encode(f"{config.DATAFORSEO_LOGIN}:{config.DATAFORSEO_PASSWORD}".encode()).decode()
        return f"Basic {token}"
    raise TrendsError(
        "No DataForSEO credentials. Set DATAFORSEO_AUTH (the 'Basic ...' value) "
        "or DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD in the environment."
    )


def fetch_company(company: str, date_from: str, date_to: str, session=None, retries: int = 3) -> dict[str, float]:
    """Return ``{iso_date: value}`` for one keyword."""
    session = session or requests.Session()
    payload = json.dumps([{
        "date_from": date_from,
        "date_to": date_to,
        "keywords": [company],
        "location_code": LOCATION_US,
        "language_code": "en",
    }])
    headers = {"Authorization": auth_header(), "Content-Type": "application/json"}
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.post(URL, headers=headers, data=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            task = data["tasks"][0]
            if task.get("status_code", 20000) != 20000:
                raise TrendsError(f"{company}: task status {task.get('status_code')} {task.get('status_message')}")
            items = task["result"][0]["items"]
            series = next(i for i in items if i.get("type", "google_trends_graph") == "google_trends_graph")
            out: dict[str, float] = {}
            for point in series["data"]:
                v = point.get("values") or []
                if not v or v[0] is None:
                    continue
                out[point["date_to"][:10]] = float(v[0])
            if not out:
                raise TrendsError(f"{company}: empty series")
            return out
        except (requests.RequestException, KeyError, IndexError, StopIteration, ValueError, TrendsError) as e:
            last_err = e
            log.warning("fetch %s attempt %d failed: %s", company, attempt + 1, e)
            time.sleep(2 ** attempt)
    raise TrendsError(f"{company}: giving up ({last_err})")


def fetch_grab(companies: Iterable[str] | None = None, lookback_days: int | None = None,
               fetcher: Callable[[str, str, str], dict[str, float]] | None = None) -> tuple[dict, list[str]]:
    """Fetch every company. Returns ``(grab, failed_companies)``.

    ``fetcher`` can be swapped for a fake in tests.
    """
    companies = list(companies or config.COMPANIES)
    lookback_days = lookback_days or config.LOOKBACK_DAYS
    today = datetime.now(timezone.utc).date()
    date_from = (today - timedelta(days=lookback_days)).isoformat()
    date_to = today.isoformat()
    session = requests.Session()
    fetcher = fetcher or (lambda c, a, b: fetch_company(c, a, b, session=session))

    grab: dict[str, dict[str, float]] = {}
    failed: list[str] = []
    for c in companies:
        try:
            grab[c] = fetcher(c, date_from, date_to)
        except Exception as e:  # noqa: BLE001 - we want to keep going for the others
            log.error("fetch %s failed: %s", c, e)
            failed.append(c)
    return grab, failed
