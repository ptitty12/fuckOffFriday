"""Runtime configuration, all via environment variables."""
import os
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Where the SQLite file lives. docker-compose points this at a volume.
DB_PATH = os.environ.get("FOF_DB_PATH", os.path.join(BASE_DIR, "productivity.db"))

# Timezone used for "today", hour-of-day calibration bands and display.
TZ_NAME = os.environ.get("FOF_TZ", "America/Chicago")
TZ = ZoneInfo(TZ_NAME)

# Companies whose search interest we treat as a proxy for "people are working".
COMPANIES = [c.strip() for c in os.environ.get("FOF_COMPANIES", "Salesforce,Oracle,Workday").split(",") if c.strip()]

# DataForSEO credentials. Either the ready-made "Basic xxx" header value, or
# login + password which we encode ourselves. Never commit these.
DATAFORSEO_AUTH = os.environ.get("DATAFORSEO_AUTH", "").strip()
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN", "").strip()
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD", "").strip()

# How many days of history each grab asks Google Trends for. Must stay above
# ~8 days (daily granularity) and below ~270 (weekly granularity kicks in).
LOOKBACK_DAYS = int(os.environ.get("FOF_LOOKBACK_DAYS", "90"))

# Scheduler cadence, in hours, for scheduler.py.
UPDATE_INTERVAL_HOURS = float(os.environ.get("FOF_UPDATE_INTERVAL_HOURS", "3"))

LOG_PATH = os.environ.get("FOF_LOG_PATH", os.path.join(BASE_DIR, "productivity_update.log"))

# History that ships with the repo; copied to DB_PATH when that file does not exist yet.
SEED_DB = os.path.join(BASE_DIR, "productivity.db")

LEGACY_CSV = os.path.join(BASE_DIR, "allHistoricals.csv")
