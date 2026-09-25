"""schema.sql and seed.sql load cleanly and match what the API expects."""
from tests.conftest import ROOT
from tests.test_access import as_user

SEED = ROOT / "backend" / "database" / "seed.sql"
SCHEMA = ROOT / "backend" / "database" / "schema.sql"


def test_schema_can_be_re_run(db):
    db.cursor().execute(SCHEMA.read_text(encoding="utf-8"))     # CREATE ... IF NOT EXISTS


def test_every_table_the_backend_uses_exists(db):
    cur = db.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    tables = {r[0] for r in cur.fetchall()}
    assert {"classes", "students", "staff", "visitors", "users", "webauthn_credentials"} <= tables


def test_seed_data_is_served_by_the_api(client, db, login):
    db.cursor().execute(SEED.read_text(encoding="utf-8"))
    token = login("admin")
    students = client.get("/students", **as_user(token)).json()["students"]
    assert [s["roll_number"] for s in students] == ["DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004"]
    assert students[0]["class_name"] == "Grade 9 - A"
    assert all(s["name"].startswith("Demo ") for s in students)          # fictional people only
    visitors = client.get("/visitors", **as_user(token)).json()["visitors"]
    assert {v["status"] for v in visitors} == {"checked_in", "overstayed"}


def test_seeded_teacher_sees_their_class(client, db, login):
    db.cursor().execute(SEED.read_text(encoding="utf-8"))
    token = login("teacher", username="teacher1", full_name="Demo Teacher One", staff_id=1)
    r = client.get("/secure/my-class-roster", **as_user(token))
    assert r.status_code == 200
    assert r.json()["class_name"] == "Grade 9 - A"
    assert [s["name"] for s in r.json()["students"]] == ["Demo Student Alpha", "Demo Student Bravo"]


def test_deleting_a_class_in_use_is_refused(client, db, login):
    db.cursor().execute(SEED.read_text(encoding="utf-8"))
    token = login("admin")
    r = client.delete("/classes/1", **as_user(token))                   # 2 students + the demo teacher
    assert r.status_code == 409
    assert r.json()["detail"] == "This class still has 2 students and 1 teacher assigned. Reassign them first."
    students = client.get("/students", **as_user(token)).json()["students"]
    assert students[0]["class_id"] == 1                                   # nothing changed
