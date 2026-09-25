"""Events older than EVENT_RETENTION_DAYS are deleted: at startup, on a
schedule, and by the purge_events.py script."""
import os
import subprocess
import sys
import time

import pytest

from backend.tracking import event_store
from tests.conftest import ROOT


def add_events(db, ages_in_days):
    cur = db.cursor()
    for age in ages_in_days:
        cur.execute("INSERT INTO events (event_type, label, created_at) "
                    "VALUES ('entry', %s, now() - make_interval(days => %s));", (f"{age} days old", age))


def labels(db):
    cur = db.cursor()
    cur.execute("SELECT label FROM events ORDER BY created_at;")
    return [r[0] for r in cur.fetchall()]


def test_older_events_are_deleted_newer_ones_kept(db):
    add_events(db, [200, 91, 89, 1, 0])
    assert event_store.purge_old_events(90) == 2
    assert labels(db) == ["89 days old", "1 days old", "0 days old"]
    assert event_store.purge_old_events(90) == 0                     # nothing left to delete


def test_default_and_setting(db, monkeypatch):
    add_events(db, [40, 10])
    monkeypatch.delenv("EVENT_RETENTION_DAYS", raising=False)
    assert event_store.retention_days() == 90
    assert event_store.purge_old_events() == 0
    monkeypatch.setenv("EVENT_RETENTION_DAYS", "30")
    assert event_store.purge_old_events() == 1
    assert labels(db) == ["10 days old"]


def test_large_backlogs_are_deleted_in_batches(db, monkeypatch):
    monkeypatch.setattr(event_store, "PURGE_BATCH", 7)
    add_events(db, [100] * 30 + [5])
    assert event_store.purge_old_events(90) == 30
    assert labels(db) == ["5 days old"]


@pytest.mark.parametrize("bad", ["0", "-5", "abc", "", "1.5"])
def test_invalid_setting_is_refused(bad):
    with pytest.raises(RuntimeError, match="EVENT_RETENTION_DAYS"):
        event_store.retention_days(bad)


def test_the_schedule_purges_at_start_and_repeats(monkeypatch):
    runs = []
    monkeypatch.setattr(event_store, "purge_old_events", lambda: runs.append(time.time()) or 0)
    event_store.start_retention(interval_seconds=0.2)
    try:
        time.sleep(0.5)
    finally:
        event_store.stop_retention()
        event_store._retention_thread.join(2)
    assert len(runs) >= 2                                              # immediately, then again


def test_the_api_starts_the_schedule(db, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api.main import app

    started = []
    monkeypatch.setattr(event_store, "start_retention", lambda *a, **k: started.append(True))
    with TestClient(app):
        pass
    assert started == [True]


def test_a_bad_setting_stops_the_api_starting(db, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api.main import app

    monkeypatch.setenv("EVENT_RETENTION_DAYS", "forever")
    with pytest.raises(RuntimeError, match="EVENT_RETENTION_DAYS"):
        with TestClient(app):
            pass


def test_purge_script(db):
    add_events(db, [120, 3])
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    r = subprocess.run([sys.executable, "backend/database/purge_events.py", "--days", "90"],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "Deleted 1 event older than 90 days."
    assert labels(db) == ["3 days old"]
    bad = subprocess.run([sys.executable, "backend/database/purge_events.py", "--days", "0"],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert bad.returncode != 0 and "EVENT_RETENTION_DAYS" in bad.stderr
