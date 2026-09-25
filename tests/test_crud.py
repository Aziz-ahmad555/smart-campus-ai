"""Create / edit / delete for students, staff, classes and visitors (as admin)."""
import pytest

from tests.test_access import as_user


@pytest.fixture
def admin(login):
    return as_user(login("admin"))


# ---- classes ----

def test_class_lifecycle(client, admin):
    r = client.post("/classes", json={"name": "Grade 9 - A", "grade_level": "9", "section": "A"}, **admin)
    assert r.status_code == 200
    created = r.json()["class"]
    assert created["name"] == "Grade 9 - A" and created["id"] == 1

    assert client.get("/classes", **admin).json()["classes"] == [created]
    assert client.delete("/classes/1", **admin).json() == {"deleted": True}
    assert client.get("/classes", **admin).json()["classes"] == []
    assert client.delete("/classes/1", **admin).status_code == 404


def test_class_name_is_required(client, admin):
    assert client.post("/classes", json={"grade_level": "9"}, **admin).status_code == 422


# ---- students ----

def test_student_lifecycle(client, admin):
    client.post("/classes", json={"name": "Grade 9 - A"}, **admin)
    new = {"name": "Test Student", "roll_number": "T-001", "photo_folder": "TestStudent", "class_id": 1}
    r = client.post("/students", json=new, **admin)
    assert r.status_code == 200
    student = r.json()["student"]
    assert {k: student[k] for k in new} == new and student["created_at"]

    listed = client.get("/students", **admin).json()["students"]
    assert len(listed) == 1 and listed[0]["class_name"] == "Grade 9 - A"

    edit = {**new, "name": "Renamed Student", "class_id": None}
    r = client.put(f"/students/{student['id']}", json=edit, **admin)
    assert r.status_code == 200 and r.json()["student"]["name"] == "Renamed Student"
    assert client.get("/students", **admin).json()["students"][0]["class_name"] is None

    assert client.delete(f"/students/{student['id']}", **admin).json() == {"deleted": True}
    assert client.get("/students", **admin).json()["students"] == []


def test_duplicate_roll_number_is_400(client, admin):
    new = {"name": "A", "roll_number": "T-001", "photo_folder": "A"}
    assert client.post("/students", json=new, **admin).status_code == 200
    r = client.post("/students", json={**new, "name": "B"}, **admin)
    assert r.status_code == 400 and r.json()["detail"] == "Roll number already exists"


def test_missing_student_is_404(client, admin):
    body = {"name": "A", "roll_number": "T-1", "photo_folder": "A"}
    assert client.put("/students/99", json=body, **admin).status_code == 404
    assert client.delete("/students/99", **admin).status_code == 404


def test_student_fields_are_validated(client, admin):
    assert client.post("/students", json={"name": "No roll"}, **admin).status_code == 422
    assert client.post("/students", json={"name": "A", "roll_number": "1", "photo_folder": "A", "class_id": "x"},
                       **admin).status_code == 422


# ---- staff ----

def test_staff_lifecycle(client, admin):
    new = {"name": "Test Teacher", "role": "Teacher", "department": "Science", "photo_folder": "TestTeacher"}
    r = client.post("/staff", json=new, **admin)
    assert r.status_code == 200
    person = r.json()["staff"]
    assert {k: person[k] for k in new} == new

    r = client.put(f"/staff/{person['id']}", json={**new, "role": "Security", "department": None}, **admin)
    assert r.status_code == 200
    assert (r.json()["staff"]["role"], r.json()["staff"]["department"]) == ("Security", None)

    assert client.delete(f"/staff/{person['id']}", **admin).json() == {"deleted": True}
    assert client.get("/staff", **admin).json()["staff"] == []
    assert client.put(f"/staff/{person['id']}", json=new, **admin).status_code == 404
    assert client.delete(f"/staff/{person['id']}", **admin).status_code == 404


# ---- visitors ----

def test_visitor_check_in_and_out(client, admin):
    r = client.post("/visitors", json={"name": "Test Visitor", "reason": "Meeting", "allowed_minutes": 30}, **admin)
    assert r.status_code == 200
    visitor = r.json()["visitor"]
    assert visitor["check_out_time"] is None

    listed = client.get("/visitors", **admin).json()["visitors"]
    assert listed[0]["status"] == "checked_in" and listed[0]["expiry_time"]

    r = client.put(f"/visitors/{visitor['id']}/checkout", **admin)
    assert r.status_code == 200 and r.json()["visitor"]["check_out_time"] is not None
    assert client.get("/visitors", **admin).json()["visitors"][0]["status"] == "checked_out"

    assert client.delete(f"/visitors/{visitor['id']}", **admin).json() == {"deleted": True}
    assert client.put(f"/visitors/{visitor['id']}/checkout", **admin).status_code == 404
    assert client.delete(f"/visitors/{visitor['id']}", **admin).status_code == 404


def test_overstayed_visitor(client, admin, db):
    db.cursor().execute(
        "INSERT INTO visitors (name, allowed_minutes, check_in_time) "
        "VALUES ('Late Visitor', 15, CURRENT_TIMESTAMP - INTERVAL '1 hour');"
    )
    assert client.get("/visitors", **admin).json()["visitors"][0]["status"] == "overstayed"


@pytest.mark.parametrize("minutes", [0, -5, 1441])
def test_visitor_duration_is_validated(client, admin, minutes):
    r = client.post("/visitors", json={"name": "Bad", "allowed_minutes": minutes}, **admin)
    assert r.status_code == 422
