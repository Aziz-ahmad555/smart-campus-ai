"""Text limits match the database columns: at the limit is accepted, one
character over is a 422 (never a database error / 500)."""
import pytest

from tests.test_access import as_user

LIMITS = {
    "/students": ({"name": 100, "roll_number": 50, "photo_folder": 100},
                  {"name": "N", "roll_number": "R", "photo_folder": "P"}),
    "/staff": ({"name": 100, "role": 50, "department": 100, "photo_folder": 100},
               {"name": "N", "role": "Teacher", "photo_folder": "P"}),
    "/classes": ({"name": 50, "grade_level": 20, "section": 10}, {"name": "N"}),
    "/visitors": ({"name": 100, "cnic_or_id": 50, "reason": 255, "host_name": 100}, {"name": "N"}),
}
CASES = [(path, field, limit) for path, (fields, _) in LIMITS.items() for field, limit in fields.items()]


@pytest.fixture
def admin(login):
    return as_user(login("admin"))


@pytest.mark.parametrize("path,field,limit", CASES)
def test_at_the_limit_is_accepted(client, admin, path, field, limit):
    body = {**LIMITS[path][1], field: "x" * limit}
    r = client.post(path, json=body, **admin)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("path,field,limit", CASES)
def test_one_over_the_limit_is_422(client, admin, path, field, limit):
    body = {**LIMITS[path][1], field: "x" * (limit + 1)}
    r = client.post(path, json=body, **admin)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == field


@pytest.mark.parametrize("path", ["/students", "/staff", "/classes", "/visitors"])
def test_required_text_cannot_be_empty(client, admin, path):
    body = {**LIMITS[path][1], "name": ""}
    assert client.post(path, json=body, **admin).status_code == 422


def test_edits_are_limited_too(client, admin):
    s = client.post("/students", json=LIMITS["/students"][1], **admin).json()["student"]
    r = client.put(f"/students/{s['id']}", json={**LIMITS["/students"][1], "roll_number": "x" * 51}, **admin)
    assert r.status_code == 422
    p = client.post("/staff", json=LIMITS["/staff"][1], **admin).json()["staff"]
    r = client.put(f"/staff/{p['id']}", json={**LIMITS["/staff"][1], "name": "x" * 101}, **admin)
    assert r.status_code == 422


def test_sign_in_inputs_are_limited(client):
    assert client.post("/login", json={"username": "x" * 51, "password": "p"}).status_code == 422
    assert client.post("/webauthn/login/begin", params={"username": "x" * 51}).status_code == 422
