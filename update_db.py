#!/usr/bin/env python3
"""Grab Google Trends once and store it. Safe to run as often as you like.

    python update_db.py            # one grab
    python update_db.py --rebuild  # recompute derived tables from the archive

Every run is archived in full, so the meter can compare today's partial-day
reading against how the same hour looked on previous days.
"""
from __future__ import annotations

import argparse
import logging
import sys

import config
import database
import trends


def setup_logging() -> None:
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(config.LOG_PATH))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=handlers)


def run_update(fetcher=None) -> int | None:
    """Fetch + ingest one grab. Returns the grab id, or None on failure."""
    log = logging.getLogger("update")
    database.init_db()
    conn = database.connect()
    run_id = database.start_run(conn)
    try:
        log.info("Starting grab for %s", ", ".join(config.COMPANIES))
        grab, failed = trends.fetch_grab(fetcher=fetcher)
        if not grab:
            raise trends.TrendsError("every company failed: " + ", ".join(failed))
        note = f"failed: {', '.join(failed)}" if failed else ""
        grab_id = database.ingest_grab(grab, database.utcnow(), source="dataforseo", note=note, conn=conn)
        database.finish_run(conn, run_id, ok=not failed, grab_id=grab_id, error=note)
        log.info("Stored grab %s (%d companies, last date %s)%s",
                 grab_id, len(grab), max(max(s) for s in grab.values()), f" [{note}]" if note else "")
        return grab_id
    except Exception as e:  # noqa: BLE001
        log.error("Update failed: %s", e, exc_info=True)
        database.finish_run(conn, run_id, ok=False, error=str(e))
        return None
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rebuild", action="store_true", help="recompute daily_scores/partial_readings from the raw archive")
    args = parser.parse_args(argv)
    setup_logging()
    if args.rebuild:
        database.init_db()
        database.rebuild_derived()
        logging.getLogger("update").info("Rebuilt derived tables")
        return 0
    return 0 if run_update() is not None else 1


if __name__ == "__main__":
    sys.exit(main())
