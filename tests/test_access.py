"""Every data endpoint requires a session (401) and the right role (403)."""
import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import fake_engine


def as_user(token):
    return {"params": {"token": token}}


ADMIN_ONLY = [
    ("GET", "/students"), ("POST", "/students"), ("PUT", "/students/1"), ("DELETE", "/students/1"),
    ("GET", "/staff"), ("POST", "/staff"), ("PUT", "/staff/1"), ("DELETE", "/staff/1"),
    ("GET", "/classes"), ("POST", "/classes"), ("DELETE", "/classes/1"),
    ("GET", "/visitors"), ("POST", "/visitors"), ("PUT", "/visitors/1/checkout"), ("DELETE", "/visitors/1"),
    ("GET", "/events"), ("POST", "/stream-ticket?purpose=video"),
]
TEACHER_ONLY = [("GET", "/my-class-roster"), ("GET", "/secure/my-class-roster")]
ANY_SIGNED_IN = [("GET", "/me"), ("GET", "/secure/my-events"), ("POST", "/logout")]


@pytest.mark.parametrize("method,path", ADMIN_ONLY + TEACHER_ONLY + ANY_SIGNED_IN)
def test_no_session_is_401(client, method, path):
    assert client.request(method, path).status_code == 401
    assert client.request(method, path, params={"token": "not-a-real-token"}).status_code == 401


@pytest.mark.parametrize("role", ["teacher", "student"])
@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_admin_endpoints_reject_other_roles(client, login, role, method, path):
    token = login(role)
    assert client.request(method, path, **as_user(token)).status_code == 403


@pytest.mark.parametrize("role", ["admin", "student"])
@pytest.mark.parametrize("method,path", TEACHER_ONLY)
def test_teacher_endpoints_reject_other_roles(client, login, role, method, path):
    assert client.request(method, path, **as_user(login(role))).status_code == 403


def test_admin_can_read_directory(client, login):
    token = login("admin")
    for path in ("/students", "/staff", "/classes", "/visitors", "/events"):
        assert client.get(path, **as_user(token)).status_code == 200, path


def test_public_endpoints_stay_public(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200


# ---- camera feed and WebSocket: single-use tickets ----

def ticket(client, token, purpose):
    r = client.post("/stream-ticket", params={"purpose": purpose, "token": token})
    assert r.status_code == 200, r.text
    return r.json()["ticket"]


def test_video_feed_needs_a_valid_ticket(client, login, monkeypatch):
    from backend.api import main

    # TestClient reads a streaming body to the end, so use a finite stream here.
    monkeypatch.setattr(main, "mjpeg_generator", lambda token: iter([b"--frame\r\n"]))
    assert client.get("/video-feed").status_code == 401
    assert client.get("/video-feed", params={"ticket": "forged"}).status_code == 401

    token = login("admin")
    events_ticket = ticket(client, token, "events")
    assert client.get("/video-feed", params={"ticket": events_ticket}).status_code == 401   # wrong purpose

    good = ticket(client, token, "video")
    r = client.get("/video-feed", params={"ticket": good})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert client.get("/video-feed", params={"ticket": good}).status_code == 401           # single use


def test_video_stream_stops_when_the_session_ends(client, login):
    from backend.api import auth, main

    token = login("admin")
    frames = main.mjpeg_generator(token)
    assert b"fake-jpeg" in next(frames)
    auth.end_session(token)
    with pytest.raises(StopIteration):
        next(frames)


def test_expired_ticket_is_refused(client, login, monkeypatch):
    from backend.api import auth

    token = login("admin")
    t = ticket(client, token, "video")
    monkeypatch.setattr(auth.time, "time", lambda: 10**12)          # far in the future
    assert auth.redeem_ticket(t, "video") is None


def test_unknown_stream_purpose_is_400(client, login):
    r = client.post("/stream-ticket", params={"purpose": "microphone", "token": login("admin")})
    assert r.status_code == 400


def test_websocket_refuses_missing_or_reused_ticket(client, login):
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws/events"):
            pass
    assert closed.value.code == 4401

    token = login("admin")
    t = ticket(client, token, "events")
    with client.websocket_connect(f"/ws/events?ticket={t}"):
        assert len(fake_engine.connected_websockets) == 1
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/events?ticket={t}"):      # already used
            pass


def test_logout_invalidates_the_session(client, login):
    token = login("admin")
    assert client.get("/students", **as_user(token)).status_code == 200
    assert client.post("/logout", **as_user(token)).status_code == 200
    assert client.get("/students", **as_user(token)).status_code == 401
