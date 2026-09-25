"""Persist recognition events to PostgreSQL without slowing the camera loop.

The tracking loop calls `enqueue(event)`, which only puts the event on an
in-memory queue (never blocks, never touches the database). A background
thread drains the queue and writes events in batches with one multi-row
INSERT. If the database is unreachable the batch is kept and retried, so a
short outage doesn't lose events; if the queue ever fills up (a very long
outage) new events are dropped and counted rather than blocking the camera.
"""
import os
import queue
import threading
import time
from datetime import datetime

import psycopg2.errors
import psycopg2.extras

from backend.api.db import get_db_connection

# Event types used by the engine/UI  <->  values stored in events.event_type
TYPE_TO_DB = {"ENTRY": "entry", "EXIT": "exit", "CROWD_ALERT": "alert", "FALL_DETECTED": "fall"}
DB_TO_TYPE = {v: k for k, v in TYPE_TO_DB.items()}

CAMERA_NAME = os.getenv("CAMERA_NAME", "main")
BATCH_SIZE = 100
FLUSH_INTERVAL = 1.0      # seconds between writes when events trickle in
RETRY_DELAY = 5.0         # seconds to wait after a failed write
QUEUE_LIMIT = 10_000

_queue = queue.Queue(maxsize=QUEUE_LIMIT)
_stop = threading.Event()
_thread = None
_unwritten = 0                    # queued or in a batch, not yet in the database
_count_lock = threading.Lock()
stats = {"written": 0, "dropped": 0, "failed_batches": 0, "unlinked": 0}

INSERT_SQL = (
    "INSERT INTO events (event_type, student_id, staff_id, label, track_id, camera, confidence, created_at) VALUES %s"
)


def to_row(event):
    person_type, person_id = event.get("person_type"), event.get("person_id")
    return (
        TYPE_TO_DB[event["type"]],
        person_id if person_type == "student" else None,
        person_id if person_type == "staff" else None,
        event.get("label") or "",
        event.get("track_id"),
        event.get("camera") or CAMERA_NAME,
        event.get("confidence"),
        datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S"),
    )


def enqueue(event):
    """Called from the camera loop: O(1), never blocks."""
    global _unwritten
    try:
        _queue.put_nowait(event)
        with _count_lock:
            _unwritten += 1
    except queue.Full:
        stats["dropped"] += 1


def _unlinked(row):
    # (event_type, student_id, staff_id, ...) with the person link removed
    return (row[0], None, None) + row[3:]


def write_batch(events):
    """One multi-row INSERT. If the database refuses it because a person was
    deleted after they were recognized, write row by row and keep those
    events without the link (the label still says who it was) instead of
    retrying the whole batch forever."""
    global _unwritten
    rows = [to_row(e) for e in events]
    conn = get_db_connection()
    try:
        try:
            with conn, conn.cursor() as cur:
                psycopg2.extras.execute_values(cur, INSERT_SQL, rows)
        except psycopg2.errors.ForeignKeyViolation:
            for row in rows:
                try:
                    with conn, conn.cursor() as cur:
                        psycopg2.extras.execute_values(cur, INSERT_SQL, [row])
                except psycopg2.errors.ForeignKeyViolation:
                    with conn, conn.cursor() as cur:
                        psycopg2.extras.execute_values(cur, INSERT_SQL, [_unlinked(row)])
                    stats["unlinked"] += 1
    finally:
        conn.close()
    stats["written"] += len(events)
    with _count_lock:
        _unwritten -= len(events)


def _drain(max_items):
    batch = []
    while len(batch) < max_items:
        try:
            batch.append(_queue.get_nowait())
        except queue.Empty:
            break
    return batch


def _run():
    pending = []
    while not _stop.is_set() or pending or not _queue.empty():
        if len(pending) < BATCH_SIZE:
            try:
                pending.append(_queue.get(timeout=FLUSH_INTERVAL))
            except queue.Empty:
                pass
            pending.extend(_drain(BATCH_SIZE - len(pending)))
        if not pending:
            continue
        try:
            write_batch(pending)
            pending = []
        except Exception as e:           # database down: keep the batch, retry later
            stats["failed_batches"] += 1
            print(f"[event_store] write failed ({len(pending)} events kept for retry): {e}")
            if _stop.is_set():
                break
            _stop.wait(RETRY_DELAY)


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, name="event-store", daemon=True)
    _thread.start()


def stop(timeout=5.0):
    """Flush what's queued and stop the writer (called on shutdown)."""
    _stop.set()
    if _thread:
        _thread.join(timeout)


def flush(timeout=5.0):
    """Wait until everything queued so far is in the database. True if it is."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _count_lock:
            if _unwritten == 0:
                return True
        time.sleep(0.01)
    return False


# ---- reading ----

EVENT_COLUMNS = "id, event_type, student_id, staff_id, label, track_id, camera, confidence, created_at"


def row_to_event(row):
    person_type = "student" if row["student_id"] else "staff" if row["staff_id"] else None
    return {
        "id": row["id"],
        "type": DB_TO_TYPE[row["event_type"]],
        "track_id": row["track_id"],
        "label": row["label"],
        "person_type": person_type,
        "person_id": row["student_id"] or row["staff_id"],
        "camera": row["camera"],
        "confidence": row["confidence"],
        "timestamp": row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
    }


def query_events(where="TRUE", params=(), limit=100, before=None):
    """Newest-first page of events. `before` is the id of the last event of
    the previous page (keyset pagination: stable while new events arrive).
    Returns (events, next_before) where next_before is None on the last page."""
    sql = f"SELECT {EVENT_COLUMNS} FROM events WHERE ({where})"
    args = list(params)
    if before is not None:
        sql += " AND id < %s"
        args.append(before)
    sql += " ORDER BY id DESC LIMIT %s"
    args.append(limit + 1)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, args)
            rows = cur.fetchall()
    finally:
        conn.close()
    page = [row_to_event(r) for r in rows[:limit]]
    return page, (page[-1]["id"] if len(rows) > limit else None)
