"""Events are stored in PostgreSQL without blocking the camera loop, and read
back per role with pagination."""
import queue
import time

import pytest

from tests.conftest import ROOT, fake_engine, insert_event
from tests.test_access import as_user
from tests.test_identity import add_people

MIGRATION = ROOT / "backend" / "database" / "migrations" / "002_events_table.sql"


def live_event(type_, label, person_type=None, person_id=None, confidence=None, track_id=1):
    return {"type": type_, "track_id": track_id, "label": label, "person_type": person_type,
            "person_id": person_id, "confidence": confidence, "camera": "gate-1",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}


# ---- writing ----

def test_writer_stores_every_kind_of_event(db, event_writer):
    add_people(db)
    event_writer.enqueue(live_event("ENTRY", "Ali (R-1)", "student", 1, confidence=0.91))
    event_writer.enqueue(live_event("EXIT", "Teacher A (Teacher)", "staff", 1))
    event_writer.enqueue(live_event("CROWD_ALERT", "3 people detected in frame", track_id=None))
    event_writer.enqueue(live_event("FALL_DETECTED", "Unknown — possible fall detected"))
    assert event_writer.flush(10)

    cur = db.cursor()
    cur.execute("SELECT event_type, student_id, staff_id, label, track_id, camera, confidence IS NOT NULL FROM events ORDER BY id;")
    assert [tuple(r) for r in cur.fetchall()] == [
        ("entry", 1, None, "Ali (R-1)", 1, "gate-1", True),
        ("exit", None, 1, "Teacher A (Teacher)", 1, "gate-1", False),
        ("alert", None, None, "3 people detected in frame", None, "gate-1", False),
        ("fall", None, None, "Unknown — possible fall detected", 1, "gate-1", False),
    ]


def test_enqueue_never_waits_for_a_slow_database(db, event_writer, monkeypatch):
    real_write = event_writer.write_batch

    def slow_write(events):
        time.sleep(0.5)                      # a sluggish database
        real_write(events)

    monkeypatch.setattr(event_writer, "write_batch", slow_write)
    start = time.perf_counter()
    for i in range(1000):
        event_writer.enqueue(live_event("ENTRY", f"Unknown {i}"))
    elapsed = time.perf_counter() - start
    assert elapsed < 0.2, f"enqueueing 1000 events took {elapsed:.3f}s"    # the camera loop isn't held up
    assert event_writer.flush(20)
    cur = db.cursor()
    cur.execute("SELECT count(*) FROM events;")
    assert cur.fetchone()[0] == 1000


def test_events_survive_a_database_outage(db, event_writer, monkeypatch):
    real_write = event_writer.write_batch
    calls = {"n": 0}

    def flaky_write(events):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("database is restarting")
        real_write(events)

    monkeypatch.setattr(event_writer, "RETRY_DELAY", 0.05)
    monkeypatch.setattr(event_writer, "write_batch", flaky_write)
    event_writer.enqueue(live_event("ENTRY", "Unknown"))
    assert event_writer.flush(10)
    cur = db.cursor()
    cur.execute("SELECT count(*) FROM events;")
    assert cur.fetchone()[0] == 1 and calls["n"] >= 2


def test_a_full_queue_drops_instead_of_blocking(monkeypatch):
    from backend.tracking import event_store

    monkeypatch.setattr(event_store, "_queue", queue.Queue(maxsize=2))
    dropped, unwritten = event_store.stats["dropped"], event_store._unwritten
    start = time.perf_counter()
    for _ in range(5):
        event_store.enqueue(live_event("ENTRY", "Unknown"))
    assert time.perf_counter() - start < 0.05
    assert event_store.stats["dropped"] == dropped + 3
    event_store._unwritten = unwritten        # the 2 queued here are thrown away with this test's queue


# ---- reading with pagination ----

def test_admin_pages_through_all_events_newest_first(client, db, login):
    for i in range(250):
        insert_event(db, "entry", f"Person {i}", created_at=f"2026-09-25 10:{i // 60:02d}:{i % 60:02d}")
    token = login("admin")

    seen, before = [], None
    while True:
        params = {"limit": 100} | ({"before": before} if before else {})
        body = client.get("/events", params=params, **as_user(token)).json()
        seen += body["events"]
        before = body["next_before"]
        if before is None:
            break
    assert len(seen) == 250 and len({e["id"] for e in seen}) == 250          # every event exactly once
    assert [e["label"] for e in seen[:2]] == ["Person 249", "Person 248"]      # newest first
    first = seen[0]
    assert first["type"] == "ENTRY" and first["timestamp"] == "2026-09-25 10:04:09"


def test_page_size_is_bounded(client, login):
    token = login("admin")
    assert client.get("/events", params={"limit": 0}, **as_user(token)).status_code == 422
    assert client.get("/events", params={"limit": 201}, **as_user(token)).status_code == 422
    assert client.get("/events", params={"before": 0}, **as_user(token)).status_code == 422


def test_history_comes_from_the_database_not_memory(client, db, login):
    insert_event(db, "exit", "Stored earlier")
    fake_engine.events_log.clear()                     # e.g. after a backend restart
    body = client.get("/events", **as_user(login("admin"))).json()
    assert [e["label"] for e in body["events"]] == ["Stored earlier"]


def test_student_timeline_is_paginated_and_their_own(client, db, login):
    add_people(db)
    for i in range(5):
        insert_event(db, "entry", f"Ali visit {i}", student_id=1, created_at=f"2026-09-25 09:0{i}:00")
    insert_event(db, "entry", "Ali Khan (R-2)", student_id=2)
    token = login("student", full_name="Ali", student_id=1)

    page1 = client.get("/secure/my-events", params={"limit": 3}, **as_user(token)).json()
    assert [e["label"] for e in page1["events"]] == ["Ali visit 4", "Ali visit 3", "Ali visit 2"]
    page2 = client.get("/secure/my-events", params={"limit": 3, "before": page1["next_before"]}, **as_user(token)).json()
    assert [e["label"] for e in page2["events"]] == ["Ali visit 1", "Ali visit 0"]
    assert page2["next_before"] is None
    assert all(e["person_type"] == "student" and e["person_id"] == 1 for e in page1["events"] + page2["events"])


def test_teacher_timeline_is_paginated_and_class_scoped(client, db, login):
    add_people(db)
    for i in range(4):
        insert_event(db, "entry", f"Ali {i}", student_id=1)
    insert_event(db, "entry", "Ali Khan (R-2)", student_id=2)          # not in this teacher's class
    token = login("teacher", full_name="Teacher A", staff_id=1)
    body = client.get("/secure/my-class-roster", params={"limit": 3}, **as_user(token)).json()
    assert len(body["events"]) == 3 and body["next_before"]
    rest = client.get("/secure/my-class-roster", params={"limit": 3, "before": body["next_before"]}, **as_user(token)).json()
    assert [e["label"] for e in body["events"] + rest["events"]] == ["Ali 3", "Ali 2", "Ali 1", "Ali 0"]


def test_deleting_a_person_keeps_their_events(client, db, login):
    add_people(db)
    insert_event(db, "entry", "Ali (R-1)", student_id=1)
    token = login("admin")
    assert client.delete("/students/1", **as_user(token)).status_code == 200
    events = client.get("/events", **as_user(token)).json()["events"]
    assert events[0]["label"] == "Ali (R-1)" and events[0]["person_id"] is None


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_only_admins_read_all_events(client, login, role):
    assert client.get("/events", **as_user(login(role))).status_code == 403


def test_migration_creates_the_table_and_is_re_runnable(db):
    cur = db.cursor()
    cur.execute("DROP TABLE events;")
    cur.execute(MIGRATION.read_text(encoding="utf-8"))
    cur.execute(MIGRATION.read_text(encoding="utf-8"))
    cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'events' ORDER BY indexname;")
    assert [r[0] for r in cur.fetchall()] == [
        "events_created_at_idx", "events_pkey", "events_staff_created_idx", "events_student_created_idx"]
    with pytest.raises(Exception):
        cur.execute("INSERT INTO events (event_type, label, student_id, staff_id) VALUES ('entry', 'x', 1, 1);")
