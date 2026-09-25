"""Events are matched to people by ID, never by name inside the label."""
import importlib.util
import sys
import types

from tests.conftest import ROOT, fake_engine, make_user
from tests.test_access import as_user

MIGRATION = ROOT / "backend" / "database" / "migrations" / "001_link_users_to_people.sql"


def add_people(db):
    """Two students whose names overlap ("Ali" is inside "Ali Khan")."""
    cur = db.cursor()
    cur.execute("INSERT INTO classes (name) VALUES ('Grade 9 - A'), ('Grade 10 - B');")
    cur.execute(
        "INSERT INTO students (name, roll_number, photo_folder, class_id) VALUES "
        "('Ali', 'R-1', 'Ali', 1), ('Ali Khan', 'R-2', 'AliKhan', 2);"
    )
    cur.execute("INSERT INTO staff (name, role, photo_folder, class_id) VALUES ('Teacher A', 'Teacher', 'TeacherA', 1);")


def event(type_, label, person_type=None, person_id=None):
    return {"type": type_, "track_id": 1, "label": label, "person_type": person_type,
            "person_id": person_id, "timestamp": "2026-09-25 10:00:00"}


def test_student_sees_only_their_own_events(client, db, login):
    add_people(db)
    fake_engine.events_log.extend([
        event("ENTRY", "Ali (R-1)", "student", 1),
        event("ENTRY", "Ali Khan (R-2)", "student", 2),      # name contains "Ali": must NOT match
        event("CROWD_ALERT", "3 people detected in frame"),
    ])
    token = login("student", full_name="Ali", student_id=1)
    body = client.get("/secure/my-events", **as_user(token)).json()
    assert body["linked"] is True
    assert [e["label"] for e in body["events"]] == ["Ali (R-1)"]


def test_teacher_sees_only_their_class_events(client, db, login):
    add_people(db)
    fake_engine.events_log.extend([
        event("ENTRY", "Ali (R-1)", "student", 1),
        event("EXIT", "Ali Khan (R-2)", "student", 2),        # other class
        event("ENTRY", "Teacher A (Teacher)", "staff", 1),    # staff id 1 != student id 1
    ])
    token = login("teacher", full_name="Teacher A", staff_id=1)
    body = client.get("/secure/my-class-roster", **as_user(token)).json()
    assert [s["name"] for s in body["students"]] == ["Ali"]
    assert [e["label"] for e in body["events"]] == ["Ali (R-1)"]


def test_unlinked_accounts_see_nothing(client, db, login):
    add_people(db)
    fake_engine.events_log.append(event("ENTRY", "Ali (R-1)", "student", 1))
    token = login("student", full_name="Ali")                  # same name, but not linked
    assert client.get("/secure/my-events", **as_user(token)).json() == {"events": [], "linked": False}
    teacher = login("teacher", username="t2", full_name="Teacher A")
    body = client.get("/secure/my-class-roster", **as_user(teacher)).json()
    assert body["students"] == [] and body["linked"] is False


def test_migration_backfills_unique_names_only(db):
    add_people(db)
    cur = db.cursor()
    cur.execute("INSERT INTO students (name, roll_number, photo_folder) VALUES ('Sam', 'R-3', 'Sam'), ('Sam', 'R-4', 'Sam2');")
    cur.execute("ALTER TABLE users DROP COLUMN student_id, DROP COLUMN staff_id;")    # a pre-migration database
    for username, role, full_name in [("ali", "student", "Ali"), ("sam", "student", "Sam"),
                                      ("teach", "teacher", "Teacher A"), ("nobody", "student", "Nobody")]:
        cur.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (%s, 'x', %s, %s);",
                    (username, role, full_name))

    cur.execute(MIGRATION.read_text(encoding="utf-8"))
    unlinked = {row[1] for row in cur.fetchall()}             # the migration's final report query
    assert unlinked == {"sam", "nobody"}                      # ambiguous name, no match

    cur.execute("SELECT username, student_id, staff_id FROM users ORDER BY id;")
    assert cur.fetchall() == [("ali", 1, None), ("sam", None, None), ("teach", None, 1), ("nobody", None, None)]
    cur.execute(MIGRATION.read_text(encoding="utf-8"))        # safe to run twice


# ---- the real engine attaches IDs to events ----

def load_real_engine(monkeypatch):
    """Import backend/tracking/engine.py with the camera/model libraries stubbed."""
    ultralytics = types.ModuleType("ultralytics")
    ultralytics.YOLO = lambda *a, **k: object()
    deepface = types.ModuleType("deepface")
    deepface.DeepFace = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics)
    monkeypatch.setitem(sys.modules, "deepface", deepface)
    spec = importlib.util.spec_from_file_location("real_engine", ROOT / "backend" / "tracking" / "engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_engine_resolves_students_and_staff_to_ids(db, monkeypatch):
    add_people(db)
    engine = load_real_engine(monkeypatch)
    assert engine.lookup_person("AliKhan") == {"person_type": "student", "person_id": 2, "label": "Ali Khan (R-2)"}
    assert engine.lookup_person("TeacherA") == {"person_type": "staff", "person_id": 1, "label": "Teacher A (Teacher)"}
    assert engine.lookup_person("NotInTheDatabase") is None


def test_engine_events_carry_the_person(db, monkeypatch):
    engine = load_real_engine(monkeypatch)
    engine.add_event("ENTRY", 7, "Ali (R-1)", {"person_type": "student", "person_id": 1, "label": "Ali (R-1)"})
    engine.add_event("CROWD_ALERT", None, "3 people detected in frame")
    entry, crowd = engine.events_log
    assert (entry["person_type"], entry["person_id"], entry["track_id"]) == ("student", 1, 7)
    assert (crowd["person_type"], crowd["person_id"]) == (None, None)
