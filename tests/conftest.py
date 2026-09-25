"""Test setup: a throwaway PostgreSQL cluster and a fake vision engine.

No webcam, face model or real database is touched:
- The camera/recognition engine (backend.tracking.engine) is replaced by an
  in-memory stand-in before the API is imported.
- A temporary PostgreSQL cluster is created with initdb in a temp folder
  (PostgreSQL binaries are found on PATH, via PG_BIN, or in the default
  Windows install folder), loaded with backend/database/schema.sql, and
  deleted afterwards. Set TEST_DATABASE_URL-style env vars instead
  (TEST_DB_HOST, TEST_DB_PORT, TEST_DB_NAME, TEST_DB_USER, TEST_DB_PASSWORD)
  to use an existing empty database.
"""
import glob
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCHEMA = ROOT / "backend" / "database" / "schema.sql"


# ---- fake vision engine (must exist before backend.api.main is imported) ----

fake_engine = types.ModuleType("backend.tracking.engine")
fake_engine.events_log = []
fake_engine.events_lock = threading.Lock()
fake_engine.connected_websockets = []
fake_engine.main_event_loop = None
fake_engine.start_background_tracking = lambda: None
fake_engine.get_latest_frame = lambda: b"\xff\xd8fake-jpeg\xff\xd9"
sys.modules["backend.tracking.engine"] = fake_engine


# ---- throwaway PostgreSQL ----

def _pg_bin(name):
    exe = name + (".exe" if os.name == "nt" else "")
    candidates = [os.environ.get("PG_BIN", ""), *sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin"), reverse=True)]
    for folder in candidates:
        if folder and Path(folder, exe).exists():
            return str(Path(folder, exe))
    return shutil.which(name)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def database():
    if os.environ.get("TEST_DB_NAME"):
        env = {k: os.environ.get("TEST_" + k, "") for k in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")}
        os.environ.update(env)
        _load_schema()
        yield env
        return

    initdb, pg_ctl = _pg_bin("initdb"), _pg_bin("pg_ctl")
    if not (initdb and pg_ctl):
        pytest.skip("PostgreSQL binaries (initdb/pg_ctl) not found; set PG_BIN or TEST_DB_* to run database tests")

    workdir = tempfile.mkdtemp(prefix="sentra-testdb-")
    data = os.path.join(workdir, "data")
    port = _free_port()
    # Output goes to DEVNULL/log files, never pipes: the server process
    # inherits them and would otherwise keep subprocess.run waiting forever.
    quiet = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    subprocess.run([initdb, "-D", data, "-U", "postgres", "--auth=trust", "-E", "UTF8", "--no-locale"],
                   check=True, **quiet)
    subprocess.run([pg_ctl, "-D", data, "-l", os.path.join(workdir, "pg.log"), "-w",
                    "-o", f"-p {port} -c listen_addresses=127.0.0.1", "start"], check=True, timeout=60, **quiet)
    try:
        import psycopg2

        admin = psycopg2.connect(host="127.0.0.1", port=port, dbname="postgres", user="postgres")
        admin.autocommit = True
        admin.cursor().execute("CREATE DATABASE sentra_test;")
        admin.close()
        env = {"DB_HOST": "127.0.0.1", "DB_PORT": str(port), "DB_NAME": "sentra_test", "DB_USER": "postgres", "DB_PASSWORD": ""}
        os.environ.update(env)
        _load_schema()
        yield env
    finally:
        subprocess.run([pg_ctl, "-D", data, "-m", "fast", "-w", "stop"], timeout=60, **quiet)
        time.sleep(0.5)
        shutil.rmtree(workdir, ignore_errors=True)


def _load_schema():
    from backend.api.db import get_db_connection

    conn = get_db_connection()
    conn.autocommit = True
    conn.cursor().execute(SCHEMA.read_text(encoding="utf-8"))
    conn.close()


@pytest.fixture
def db(database):
    """A connection to the test database, emptied before each test."""
    from backend.api.db import get_db_connection

    conn = get_db_connection()
    conn.autocommit = True
    conn.cursor().execute(
        "TRUNCATE events, webauthn_credentials, users, visitors, students, staff, classes RESTART IDENTITY CASCADE;"
    )
    fake_engine.events_log.clear()
    yield conn
    conn.close()


@pytest.fixture
def client(db, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api import auth
    from backend.api.main import app
    from backend.tracking import event_store

    # The scheduled retention cleanup runs in its own tests (test_retention.py).
    monkeypatch.setattr(event_store, "start_retention", lambda *a, **k: None)

    from backend.api import main

    auth._sessions.clear()
    auth._tickets.clear()
    auth.login_limiter.reset()
    main._challenges.clear()
    with TestClient(app) as c:
        yield c


# ---- helpers ----

def make_user(db, username, role, full_name=None, password="correct-horse", student_id=None, staff_id=None):
    import bcrypt

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, role, full_name, student_id, staff_id) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
        (username, hashed, role, full_name or username.title(), student_id, staff_id),
    )
    return cur.fetchone()[0]


@pytest.fixture
def login(client, db):
    """login(role) -> auth kwargs for that role's fresh session."""
    def _login(role, username=None, full_name=None, student_id=None, staff_id=None):
        username = username or f"{role}1"
        make_user(db, username, role, full_name, student_id=student_id, staff_id=staff_id)
        r = client.post("/login", json={"username": username, "password": "correct-horse"})
        assert r.status_code == 200, r.text
        return r.json()["token"]
    return _login


def insert_event(db, type_, label, student_id=None, staff_id=None, created_at="2026-09-25 10:00:00", track_id=1):
    """Put one event straight into the events table (as the writer would)."""
    cur = db.cursor()
    cur.execute(
        "INSERT INTO events (event_type, student_id, staff_id, label, track_id, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;",
        (type_, student_id, staff_id, label, track_id, created_at),
    )
    return cur.fetchone()[0]


@pytest.fixture
def event_writer(database):
    """The real background event writer, started for one test."""
    from backend.tracking import event_store

    event_store.start()
    yield event_store
    assert event_store.flush(10), "events still unwritten at the end of the test"
    event_store.stop()
