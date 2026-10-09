#!/usr/bin/env python3
"""Run the updater on a fixed cadence. Used by the `updater` docker-compose service.

Grabs several times a day on purpose: each one is archived, and the more
same-hour samples we have, the better the partial-day calibration gets.
"""
import logging
import time
from datetime import datetime, timezone

import config
from update_db import run_update, setup_logging


def main() -> None:
    setup_logging()
    log = logging.getLogger("scheduler")
    interval = max(0.25, config.UPDATE_INTERVAL_HOURS) * 3600
    log.info("Scheduler up: every %.1f h, tz %s", interval / 3600, config.TZ_NAME)
    while True:
        started = time.monotonic()
        run_update()
        # Align the next run to the cadence rather than drifting.
        sleep_for = max(60.0, interval - (time.monotonic() - started))
        log.info("Next grab at %s", datetime.fromtimestamp(time.time() + sleep_for, tz=timezone.utc).astimezone(config.TZ).strftime("%Y-%m-%d %H:%M %Z"))
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
