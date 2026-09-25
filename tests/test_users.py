"""Admin account management: list, link/unlink, remove fingerprints, delete."""
import pytest

from tests.conftest import insert_event, make_user
from tests.test_access import as_user
from tests.test_identity import add_people


@pytest.fixture
def admin(login):
    return as_user(login("admin", username="boss"))


def user_id(db, username):
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
    return cur.fetchone()[0]


def add_fingerprints(db, uid, n=1):
    cur = db.cursor()
    for i in range(n):
        cur.execute("INSERT INTO webauthn_credentials (user_id, credential_id, public_key) VALUES (%s, %s, 'k');",
                    (uid, bytes([uid, i])))


def test_list_shows_links_and_fingerprints_but_never_hashes(client, db, admin):
    add_people(db)
    add_fingerprints(db, make_user(db, "ali", "student", "Ali", student_id=1), 2)
    make_user(db, "teach", "teacher", "Teacher A")
    r = client.get("/users", **admin)
    assert r.status_code == 200
    rows = {u["username"]: u for u in r.json()["users"]}
    assert set(rows) == {"boss", "ali", "teach"}
    assert (rows["ali"]["linked_name"], rows["ali"]["linked_roll_number"], rows["ali"]["fingerprints"]) == ("Ali", "R-1", 2)
    assert rows["teach"]["linked_name"] is None
    assert "password_hash" not in r.text and "correct-horse" not in r.text


def test_link_and_unlink_a_teacher(client, db, admin):
    add_people(db)
    uid = make_user(db, "teach", "teacher", "Teacher A")
    r = client.put(f"/users/{uid}/link", json={"person_id": 1}, **admin)
    assert r.status_code == 200
    assert (r.json()["user"]["staff_id"], r.json()["user"]["linked_name"]) == (1, "Teacher A")
    r = client.put(f"/users/{uid}/link", json={"person_id": None}, **admin)
    assert r.json()["user"]["staff_id"] is None and r.json()["user"]["linked_name"] is None


def test_student_links_to_a_student_record(client, db, admin):
    add_people(db)
    uid = make_user(db, "ali", "student", "Ali")
    r = client.put(f"/users/{uid}/link", json={"person_id": 2}, **admin)
    assert (r.json()["user"]["student_id"], r.json()["user"]["staff_id"]) == (2, None)


def test_admins_cant_be_linked(client, db, admin):
    uid = make_user(db, "other-admin", "admin")
    r = client.put(f"/users/{uid}/link", json={"person_id": 1}, **admin)
    assert r.status_code == 400


def test_linking_to_a_missing_person_is_409(client, db, admin):
    uid = make_user(db, "ali", "student", "Ali")
    r = client.put(f"/users/{uid}/link", json={"person_id": 999}, **admin)
    assert r.status_code == 409 and r.json()["detail"] == "That student record doesn't exist."


def test_a_new_link_applies_to_open_sessions_immediately(client, db, admin, login):
    add_people(db)
    insert_event(db, "entry", "Ali (R-1)", student_id=1)
    student = as_user(login("student", username="ali", full_name="Ali"))
    assert client.get("/secure/my-events", **student).json()["linked"] is False
    client.put(f"/users/{user_id(db, 'ali')}/link", json={"person_id": 1}, **admin)
    body = client.get("/secure/my-events", **student).json()                 # same session, no re-login
    assert body["linked"] is True and [e["label"] for e in body["events"]] == ["Ali (R-1)"]


def test_delete_with_fingerprints_is_409_until_they_are_removed(client, db, admin, login):
    uid = make_user(db, "finger", "student")
    add_fingerprints(db, uid, 2)
    r = client.delete(f"/users/{uid}", **admin)
    assert r.status_code == 409
    assert r.json()["detail"] == ("This user has 2 registered fingerprints for sign-in. "
                                  "Remove their fingerprints first, then delete the account.")
    assert client.delete(f"/users/{uid}/fingerprints", **admin).json() == {"removed": 2}
    assert client.delete(f"/users/{uid}", **admin).json() == {"deleted": True}
    assert "finger" not in {u["username"] for u in client.get("/users", **admin).json()["users"]}


def test_deleting_an_account_signs_it_out(client, db, admin, login):
    student = as_user(login("student", username="leaver"))
    assert client.get("/me", **student).status_code == 200
    assert client.delete(f"/users/{user_id(db, 'leaver')}", **admin).status_code == 200
    assert client.get("/me", **student).status_code == 401


def test_cant_delete_yourself(client, db, admin):
    r = client.delete(f"/users/{user_id(db, 'boss')}", **admin)
    assert r.status_code == 400 and r.json()["detail"] == "You can't delete your own account."
    other = make_user(db, "second-admin", "admin")
    assert client.delete(f"/users/{other}", **admin).status_code == 200      # another admin is fine


def test_last_admin_cannot_be_deleted(client, db, login):
    helper = make_user(db, "helper-admin", "admin")
    token = client.post("/login", json={"username": "helper-admin", "password": "correct-horse"}).json()["token"]
    target = make_user(db, "only-other-admin", "admin")
    db.cursor().execute("UPDATE users SET role = 'teacher' WHERE id = %s;", (helper,))   # helper keeps an admin session
    r = client.delete(f"/users/{target}", **as_user(token))
    assert r.status_code == 400 and r.json()["detail"] == "This is the last admin account, so it can't be deleted."


def test_missing_account_is_404(client, admin):
    assert client.delete("/users/999", **admin).status_code == 404
    assert client.delete("/users/999/fingerprints", **admin).status_code == 404
    assert client.put("/users/999/link", json={"person_id": None}, **admin).status_code == 404
