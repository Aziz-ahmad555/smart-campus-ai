"""Foreign-key refusals come back as 409 with a message that says what to fix."""
import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import conflicts
from tests.conftest import make_user
from tests.test_access import as_user


@pytest.fixture
def admin(login):
    return as_user(login("admin"))


def add_class_with(db, students=0, teachers=0):
    cur = db.cursor()
    cur.execute("INSERT INTO classes (name) VALUES ('Grade 9 - A') RETURNING id;")
    class_id = cur.fetchone()[0]
    for i in range(students):
        cur.execute("INSERT INTO students (name, roll_number, photo_folder, class_id) VALUES (%s, %s, %s, %s);",
                    (f"Student {i}", f"R-{i}", f"S{i}", class_id))
    for i in range(teachers):
        cur.execute("INSERT INTO staff (name, role, photo_folder, class_id) VALUES (%s, 'Teacher', %s, %s);",
                    (f"Teacher {i}", f"T{i}", class_id))
    return class_id


# ---- deleting a class that's still in use ----

@pytest.mark.parametrize("students,teachers,expected", [
    (12, 0, "This class still has 12 students assigned. Reassign them first."),
    (1, 0, "This class still has 1 student assigned. Reassign them first."),
    (0, 1, "This class still has 1 teacher assigned. Reassign them first."),
    (2, 1, "This class still has 2 students and 1 teacher assigned. Reassign them first."),
])
def test_class_in_use_is_409_with_counts(client, db, admin, students, teachers, expected):
    class_id = add_class_with(db, students, teachers)
    r = client.delete(f"/classes/{class_id}", **admin)
    assert r.status_code == 409 and r.json()["detail"] == expected
    assert len(client.get("/classes", **admin).json()["classes"]) == 1          # still there


def test_class_can_be_deleted_once_empty(client, db, admin):
    class_id = add_class_with(db, students=1)
    assert client.delete(f"/classes/{class_id}", **admin).status_code == 409
    db.cursor().execute("UPDATE students SET class_id = NULL;")
    assert client.delete(f"/classes/{class_id}", **admin).status_code == 200


# ---- deleting a person who has a login account ----

def test_student_with_login_account_is_409(client, db, admin):
    add_class_with(db, students=1)
    make_user(db, "stud1", "student", "Student 0", student_id=1)
    r = client.delete("/students/1", **admin)
    assert r.status_code == 409
    assert r.json()["detail"] == ("This student has a login account ('stud1'). "
                                  "Remove the account or unlink it from this person before deleting them.")
    assert len(client.get("/students", **admin).json()["students"]) == 1


def test_staff_with_login_account_is_409(client, db, admin):
    add_class_with(db, teachers=1)
    make_user(db, "teach1", "teacher", "Teacher 0", staff_id=1)
    make_user(db, "teach2", "teacher", "Teacher 0", staff_id=1)
    r = client.delete("/staff/1", **admin)
    assert r.status_code == 409
    assert r.json()["detail"].startswith("This staff member has login accounts ('teach1', 'teach2').")


def test_person_without_account_can_be_deleted(client, db, admin):
    add_class_with(db, students=1)
    assert client.delete("/students/1", **admin).status_code == 200


# ---- a user with registered fingerprints ----

def add_user_with_fingerprints(db, n):
    user_id = make_user(db, "finger", "admin")
    cur = db.cursor()
    for i in range(n):
        cur.execute("INSERT INTO webauthn_credentials (user_id, credential_id, public_key) VALUES (%s, %s, %s);",
                    (user_id, bytes([i + 1]), b"key"))
    return user_id


def test_user_with_fingerprints_explained_with_count(db):
    user_id = add_user_with_fingerprints(db, 2)
    db.autocommit = False
    try:
        with pytest.raises(psycopg2.errors.ForeignKeyViolation) as refused:
            db.cursor().execute("DELETE FROM users WHERE id = %s;", (user_id,))
        with pytest.raises(Exception) as http:
            raise conflicts.conflict(refused.value, db, deleting=("users", user_id))
        assert http.value.status_code == 409
        assert http.value.detail == ("This user has 2 registered fingerprints for sign-in. "
                                     "Remove their fingerprints first, then delete the account.")
    finally:
        db.rollback()
        db.autocommit = True


def test_unhandled_refusal_is_409_not_500(db):
    """No endpoint deletes users yet; the app-wide handler covers future ones."""
    from backend.api.db import get_db_connection

    user_id = add_user_with_fingerprints(db, 1)
    app = FastAPI()
    app.add_exception_handler(psycopg2.errors.ForeignKeyViolation, conflicts.unhandled_fk_violation)

    @app.delete("/users/{uid}")
    def delete_user(uid: int):
        conn = get_db_connection()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s;", (uid,))
        finally:
            conn.close()

    r = TestClient(app).delete(f"/users/{user_id}")
    assert r.status_code == 409
    assert r.json()["detail"] == "This user has registered fingerprints for sign-in. Remove them before deleting the account."


def test_main_app_has_the_last_resort_handler():
    from backend.api.main import app

    assert app.exception_handlers[psycopg2.errors.ForeignKeyViolation] is conflicts.unhandled_fk_violation


# ---- pointing at something that doesn't exist ----

def test_student_in_missing_class_is_409(client, admin):
    body = {"name": "A", "roll_number": "R-1", "photo_folder": "A", "class_id": 99}
    r = client.post("/students", json=body, **admin)
    assert r.status_code == 409 and r.json()["detail"].startswith("That class doesn't exist")
    ok = client.post("/students", json={**body, "class_id": None}, **admin).json()["student"]
    r = client.put(f"/students/{ok['id']}", json=body, **admin)
    assert r.status_code == 409 and r.json()["detail"].startswith("That class doesn't exist")


def test_duplicate_roll_number_on_edit_is_400(client, admin):
    client.post("/students", json={"name": "A", "roll_number": "R-1", "photo_folder": "A"}, **admin)
    b = client.post("/students", json={"name": "B", "roll_number": "R-2", "photo_folder": "B"}, **admin).json()["student"]
    r = client.put(f"/students/{b['id']}", json={"name": "B", "roll_number": "R-1", "photo_folder": "B"}, **admin)
    assert r.status_code == 400 and r.json()["detail"] == "Roll number already exists"


# ---- the event writer and deleted people ----

def test_events_for_a_deleted_person_are_kept_unlinked(db, event_writer):
    import time

    add_class_with(db, students=1)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    event = lambda sid, label: {"type": "ENTRY", "track_id": 1, "label": label, "person_type": "student",  # noqa: E731
                                "person_id": sid, "timestamp": now}
    unlinked = event_writer.stats["unlinked"]
    event_writer.enqueue(event(1, "Student 0 (R-0)"))
    event_writer.enqueue(event(999, "Deleted Student (R-9)"))       # recognized, then deleted
    assert event_writer.flush(10)
    cur = db.cursor()
    cur.execute("SELECT label, student_id FROM events ORDER BY id;")
    assert cur.fetchall() == [("Student 0 (R-0)", 1), ("Deleted Student (R-9)", None)]
    assert event_writer.stats["unlinked"] == unlinked + 1
