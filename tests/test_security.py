"""Security review fixes: fingerprint sign-in is bound to its own account,
failed sign-ins lock out, no username discovery, safe CORS and headers, and
nothing secret in the logs."""
import base64
import hashlib
import json
import os
import subprocess
import sys

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from tests.conftest import ROOT, make_user
from tests.test_access import as_user


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class SoftAuthenticator:
    """A real P-256 WebAuthn credential in software: signs genuine assertions."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        numbers = self.key.public_key().public_numbers()
        self.credential_id = os.urandom(16)
        self.cose_public_key = cbor2.dumps({1: 2, 3: -7, -1: 1,
                                            -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})
        self.sign_count = 0

    def register(self, db, user_id):
        db.cursor().execute(
            "INSERT INTO webauthn_credentials (user_id, credential_id, public_key, sign_count) VALUES (%s, %s, %s, 0);",
            (user_id, self.credential_id, self.cose_public_key))

    def assertion(self, challenge, origin="http://localhost:5173", rp_id="localhost"):
        self.sign_count += 1
        client_data = json.dumps({"type": "webauthn.get", "challenge": challenge, "origin": origin,
                                  "crossOrigin": False}).encode()
        auth_data = hashlib.sha256(rp_id.encode()).digest() + bytes([0x05]) + self.sign_count.to_bytes(4, "big")
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": b64(self.credential_id), "rawId": b64(self.credential_id), "type": "public-key",
                "response": {"authenticatorData": b64(auth_data), "clientDataJSON": b64(client_data),
                             "signature": b64(signature)},
                "clientExtensionResults": {}}


def begin(client, username):
    r = client.post("/webauthn/login/begin", params={"username": username})
    assert r.status_code == 200, r.text
    body = r.json()
    return json.loads(body["options"])["challenge"], body["challenge_id"]


@pytest.fixture
def two_users(db):
    attacker, victim = SoftAuthenticator(), SoftAuthenticator()
    attacker.register(db, make_user(db, "mallory", "student"))
    victim.register(db, make_user(db, "headadmin", "admin"))
    return attacker, victim


# ---- CRITICAL: a fingerprint only signs in its own account ----

def test_own_fingerprint_signs_in(client, two_users):
    _, victim = two_users
    challenge, challenge_id = begin(client, "headadmin")
    r = client.post("/webauthn/login/complete", json={
        "username": "headadmin", "challenge_id": challenge_id, "credential": victim.assertion(challenge)})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "admin"


def test_someone_elses_fingerprint_cannot_sign_in_as_you(client, two_users):
    attacker, _ = two_users
    challenge, challenge_id = begin(client, "headadmin")         # the victim's username...
    r = client.post("/webauthn/login/complete", json={             # ...signed with the attacker's own key
        "username": "headadmin", "challenge_id": challenge_id, "credential": attacker.assertion(challenge)})
    assert r.status_code == 401
    assert "token" not in r.json()


def test_challenges_are_single_use_and_bound_to_the_username(client, two_users):
    attacker, victim = two_users
    challenge, challenge_id = begin(client, "headadmin")
    ok = client.post("/webauthn/login/complete", json={
        "username": "headadmin", "challenge_id": challenge_id, "credential": victim.assertion(challenge)})
    assert ok.status_code == 200
    replay = client.post("/webauthn/login/complete", json={
        "username": "headadmin", "challenge_id": challenge_id, "credential": victim.assertion(challenge)})
    assert replay.status_code == 400

    challenge, challenge_id = begin(client, "mallory")
    other = client.post("/webauthn/login/complete", json={
        "username": "headadmin", "challenge_id": challenge_id, "credential": attacker.assertion(challenge)})
    assert other.status_code == 400


def test_challenges_expire(client, two_users, monkeypatch):
    from backend.api import main

    _, victim = two_users
    challenge, challenge_id = begin(client, "headadmin")
    real_time = main.time.time
    monkeypatch.setattr(main.time, "time", lambda: real_time() + main.CHALLENGE_TTL_SECONDS + 1)
    r = client.post("/webauthn/login/complete", json={
        "username": "headadmin", "challenge_id": challenge_id, "credential": victim.assertion(challenge)})
    assert r.status_code == 400


def test_malformed_fingerprint_response_is_400(client, two_users):
    _, challenge_id = begin(client, "headadmin")
    r = client.post("/webauthn/login/complete", json={"username": "headadmin", "challenge_id": challenge_id, "credential": {}})
    assert r.status_code == 400


# ---- HIGH: failed sign-ins lock out ----

def test_five_failures_lock_the_account_for_fifteen_minutes(client, db, monkeypatch):
    from backend.api import auth

    make_user(db, "admin1", "admin")
    for _ in range(5):
        assert client.post("/login", json={"username": "admin1", "password": "wrong"}).status_code == 401
    locked = client.post("/login", json={"username": "admin1", "password": "correct-horse"})    # even the right one
    assert locked.status_code == 429
    assert locked.json()["detail"] == "Too many failed sign-in attempts. Try again in 15 minutes."
    assert 890 <= int(locked.headers["Retry-After"]) <= 901

    real_time = auth.time.time
    monkeypatch.setattr(auth.time, "time", lambda: real_time() + 15 * 60 + 1)
    assert client.post("/login", json={"username": "admin1", "password": "correct-horse"}).status_code == 200


def test_success_resets_the_count(client, db):
    make_user(db, "admin1", "admin")
    for _ in range(4):
        client.post("/login", json={"username": "admin1", "password": "wrong"})
    assert client.post("/login", json={"username": "admin1", "password": "correct-horse"}).status_code == 200
    for _ in range(4):
        assert client.post("/login", json={"username": "admin1", "password": "wrong"}).status_code == 401
    assert client.post("/login", json={"username": "admin1", "password": "correct-horse"}).status_code == 200


def test_unknown_usernames_count_too_and_one_address_is_limited(client):
    from backend.api import auth

    for i in range(auth.MAX_FAILED_LOGINS_PER_IP):
        client.post("/login", json={"username": f"guess{i}", "password": "x"})
    r = client.post("/login", json={"username": "somebody-new", "password": "x"})
    assert r.status_code == 429                                   # password spraying from one address


def test_fingerprint_failures_count_towards_the_lockout(client, two_users):
    attacker, _ = two_users
    for _ in range(5):
        challenge, challenge_id = begin(client, "headadmin")
        client.post("/webauthn/login/complete", json={
            "username": "headadmin", "challenge_id": challenge_id, "credential": attacker.assertion(challenge)})
    assert client.post("/login", json={"username": "headadmin", "password": "correct-horse"}).status_code == 429


# ---- HIGH: very long passwords ----

def test_password_longer_than_bcrypt_allows_is_401_not_500(client, db):
    make_user(db, "admin1", "admin")
    r = client.post("/login", json={"username": "admin1", "password": "é" * 100})       # 200 bytes
    assert r.status_code == 401


# ---- MEDIUM: no username discovery ----

def test_unknown_username_still_checks_a_password_hash(client, monkeypatch):
    from backend.api import main

    calls = []
    real = main.bcrypt.checkpw
    monkeypatch.setattr(main.bcrypt, "checkpw", lambda pw, h: calls.append(1) or real(pw, h))
    assert client.post("/login", json={"username": "nobody", "password": "x"}).status_code == 401
    assert calls == [1]                                            # same work as a real account


def test_fingerprint_begin_doesnt_reveal_which_users_exist(client, db):
    make_user(db, "no-fingerprint", "admin")
    unknown = client.post("/webauthn/login/begin", params={"username": "does-not-exist"})
    known = client.post("/webauthn/login/begin", params={"username": "no-fingerprint"})
    assert unknown.status_code == known.status_code == 400
    assert unknown.json() == known.json() == {"detail": "Fingerprint sign-in isn't set up for this account."}


def test_fingerprint_errors_dont_leak_library_details(client, two_users):
    attacker, _ = two_users
    challenge, challenge_id = begin(client, "mallory")
    bad = attacker.assertion(challenge, origin="https://evil.example")
    r = client.post("/webauthn/login/complete", json={"username": "mallory", "challenge_id": challenge_id, "credential": bad})
    assert r.status_code == 401 and r.json() == {"detail": "Fingerprint sign-in failed."}


# ---- MEDIUM: CORS and headers ----

def test_cors_allows_only_what_the_dashboard_needs(client):
    pre = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"}
    ok = client.options("/students", headers={**pre, "Access-Control-Request-Headers": "authorization,content-type"})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in ok.headers
    odd = client.options("/students", headers={**pre, "Access-Control-Request-Headers": "x-something-else"})
    assert odd.status_code == 400


def test_wildcard_origin_is_refused_at_startup():
    env = {**os.environ, "FRONTEND_ORIGIN": "*", "PYTHONPATH": str(ROOT)}
    code = ("import sys, types; sys.modules['backend.tracking.engine'] = types.ModuleType('e'); "
            "import backend.api.main")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode != 0 and "'*' is not allowed" in r.stderr


def test_security_headers_on_api_responses(client, login):
    r = client.get("/students", **as_user(login("admin")))
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in r.headers["content-security-policy"]


# ---- LOW: nothing secret in the logs ----

def test_no_passwords_or_tokens_in_logs(client, db, two_users, capfd):
    attacker, _ = two_users
    make_user(db, "admin1", "admin", password="Sup3r-Secret-Pa55")
    client.post("/login", json={"username": "admin1", "password": "wrong-Pa55-guess"})
    token = client.post("/login", json={"username": "admin1", "password": "Sup3r-Secret-Pa55"}).json()["token"]
    ticket = client.post("/stream-ticket", params={"purpose": "video"}, **as_user(token)).json()["ticket"]
    challenge, challenge_id = begin(client, "mallory")
    client.post("/webauthn/login/complete", json={"username": "mallory", "challenge_id": challenge_id,
                                                  "credential": attacker.assertion(challenge, origin="https://evil.example")})
    out, err = capfd.readouterr()
    for secret in ("Sup3r-Secret-Pa55", "wrong-Pa55-guess", token, ticket, challenge):
        assert secret not in out + err


SERVE = """
import sys, threading, types
engine = types.ModuleType("backend.tracking.engine")          # no camera or models
engine.connected_websockets, engine.main_event_loop = [], None
engine.events_log, engine.events_lock = [], threading.Lock()
engine.start_background_tracking = lambda: None
engine.wait_for_frame = lambda seq, timeout=1.0: (seq + 1, b"jpeg")
sys.modules["backend.tracking.engine"] = engine
import uvicorn
from backend.tracking import event_store
event_store.start_retention = lambda *a, **k: None
uvicorn.run("backend.api.main:app", host="127.0.0.1", port=int(sys.argv[1]))   # uvicorn's default logging
"""


def test_stream_tickets_are_redacted_in_uvicorns_logs(db):
    """The test client bypasses uvicorn, so this runs the API under a real
    uvicorn server (its own process, default logging, the throwaway test
    database) and reads what it logs: the access log (GET /video-feed) and
    the WebSocket handshake lines (/ws/events, accepted and refused)."""
    import time

    pytest.importorskip("uvicorn")
    websockets_sync = pytest.importorskip("websockets.sync.client")
    import httpx

    from tests.conftest import _free_port

    make_user(db, "admin1", "admin", password="Sup3r-Secret-Pa55")
    port = _free_port()
    base = f"127.0.0.1:{port}"
    server = subprocess.Popen([sys.executable, "-c", SERVE, str(port)], cwd=ROOT,
                              env={**os.environ, "PYTHONPATH": str(ROOT)},
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(200):
            try:
                httpx.get(f"http://{base}/health", timeout=1)
                break
            except httpx.HTTPError:
                time.sleep(0.1)
        token = httpx.post(f"http://{base}/login", json={"username": "admin1", "password": "Sup3r-Secret-Pa55"}).json()["token"]
        ticket = lambda purpose: httpx.post(f"http://{base}/stream-ticket", params={"purpose": purpose},
                                            headers={"Authorization": f"Bearer {token}"}).json()["ticket"]
        video, events, forged = ticket("video"), ticket("events"), "forged-ticket-value-123"

        with httpx.stream("GET", f"http://{base}/video-feed", params={"ticket": video}, timeout=5) as r:
            assert r.status_code == 200
        assert httpx.get(f"http://{base}/video-feed", params={"ticket": forged}, timeout=5).status_code == 401
        with websockets_sync.connect(f"ws://{base}/ws/events?ticket={events}", open_timeout=5):
            pass                                                      # accepted
        with pytest.raises(Exception):
            websockets_sync.connect(f"ws://{base}/ws/events?ticket={forged}", open_timeout=5)   # refused
        time.sleep(0.5)                                               # let the last lines be written
    finally:
        server.terminate()
        logged = server.communicate(timeout=30)[0]

    assert '"GET /video-feed?ticket=[redacted] HTTP/1.1" 200' in logged
    assert '"GET /video-feed?ticket=[redacted] HTTP/1.1" 401' in logged
    assert '"WebSocket /ws/events?ticket=[redacted]" [accepted]' in logged
    assert '"WebSocket /ws/events?ticket=[redacted]" 403' in logged
    for secret in (video, events, forged, token, "Sup3r-Secret-Pa55"):
        assert secret not in logged


def test_api_docs_get_their_own_csp(client):
    """/docs and /redoc load FastAPI's Swagger UI / ReDoc files from the CDN and
    run one inline script, so they get a policy allowing exactly that (by
    hash); every other response keeps default-src 'none'."""
    import base64
    import re

    r = client.get("/docs")
    assert r.status_code == 200 and "swagger-ui-bundle.js" in r.text
    csp = r.headers["content-security-policy"]
    inline = re.search(r"<script>(.*?)</script>", r.text, re.DOTALL).group(1)
    digest = base64.b64encode(hashlib.sha256(inline.encode()).digest()).decode()
    assert f"script-src https://cdn.jsdelivr.net 'sha256-{digest}'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]    # scripts: CDN + that hash only
    assert "connect-src 'self'" in csp and "frame-ancestors 'none'" in csp

    assert "script-src https://cdn.jsdelivr.net" in client.get("/redoc").headers["content-security-policy"]
    assert client.get("/openapi.json").headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert client.get("/health").headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
