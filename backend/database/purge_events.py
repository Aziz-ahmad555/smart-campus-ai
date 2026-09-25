"""Delete recognition events older than EVENT_RETENTION_DAYS (default 90).

The API already does this at startup and every 6 hours; run this by hand or
from a scheduler (cron / Windows Task Scheduler) if the API isn't always on.

    python backend/database/purge_events.py            # uses EVENT_RETENTION_DAYS from .env
    python backend/database/purge_events.py --days 30  # one-off override
"""
import argparse
import sys

sys.path.insert(0, ".")
from backend.tracking.event_store import purge_old_events, retention_days  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--days", help="keep this many days instead of EVENT_RETENTION_DAYS")
args = parser.parse_args()

try:
    days = retention_days(args.days) if args.days is not None else retention_days()
except RuntimeError as e:
    sys.exit(str(e))
deleted = purge_old_events(days)
print(f"Deleted {deleted} event{'s' if deleted != 1 else ''} older than {days} days.")
