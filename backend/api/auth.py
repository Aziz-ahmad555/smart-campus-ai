"""Sessions, role checks and stream tickets.

Every data endpoint depends on `current_session` or `require_role(...)`, so an
unauthenticated request gets 401 and a signed-in user with the wrong role
gets 403. The session token travels only in the `Authorization: Bearer`
header; sessions expire SESSION_TTL_SECONDS after sign-in.

The camera feed (<img>) and the live event WebSocket can't send request
headers, so they use a short-lived, single-use *stream ticket* instead of
the session token: the page asks POST /stream-ticket for one, then puts it
in the stream URL. A ticket works for one purpose, once, within 60 seconds,
and only while its session is still valid.
"""
import os
import secrets
import threading
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Sessions end this long after sign-in (SESSION_HOURS in .env, default 8).
SESSION_TTL_SECONDS = int(float(os.getenv("SESSION_HOURS", "8")) * 3600)
TICKET_TTL_SECONDS = 60
STREAM_PURPOSES = ("video", "events")

_sessions = {}   # token -> {user_id, username, role, full_name, student_id, staff_id, expires_at}
_tickets = {}    # ticket -> {token, purpose, expires_at}
_lock = threading.Lock()


def create_session(user):
    token = secrets.token_hex(32)
    with _lock:
        _sessions[token] = {
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"],
            "student_id": user.get("student_id"),   # linked person (users.student_id / staff_id)
            "staff_id": user.get("staff_id"),
            "expires_at": time.time() + SESSION_TTL_SECONDS,
        }
    return token


def get_session(token):
    if not token:
        return None
    with _lock:
        session = _sessions.get(token)
        if session and session["expires_at"] <= time.time():
            del _sessions[token]           # expired: gone for good
            session = None
        return session


def end_session(token):
    with _lock:
        _sessions.pop(token, None)
        for ticket in [t for t, v in _tickets.items() if v["token"] == token]:
            del _tickets[ticket]


def public_user(session):
    return {"username": session["username"], "role": session["role"], "full_name": session["full_name"]}


def session_expiry(session):
    return int(session["expires_at"])


# ---- FastAPI dependencies ----

_bearer = HTTPBearer(auto_error=False)


def session_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    """The session token from the `Authorization: Bearer <token>` header.
    Tokens are never accepted in the URL."""
    return credentials.credentials if credentials else None


def current_session(token: str = Depends(session_token)):
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Not signed in or session expired",
                            headers={"WWW-Authenticate": "Bearer"})
    return {**session, "token": token}


def require_role(*roles):
    def check(session=Depends(current_session)):
        if session["role"] not in roles:
            raise HTTPException(status_code=403, detail="You don't have access to this")
        return session
    return check


admin_only = require_role("admin")
teacher_only = require_role("teacher")


# ---- Stream tickets ----

def issue_ticket(token, purpose):
    if purpose not in STREAM_PURPOSES:
        raise HTTPException(status_code=400, detail=f"Unknown stream '{purpose}'")
    ticket = secrets.token_urlsafe(32)
    now = time.time()
    with _lock:
        for t in [t for t, v in _tickets.items() if v["expires_at"] < now]:
            del _tickets[t]
        _tickets[ticket] = {"token": token, "purpose": purpose, "expires_at": now + TICKET_TTL_SECONDS}
    return ticket


def redeem_ticket(ticket, purpose):
    """Returns the session token the ticket was issued to, or None. Single use."""
    if not ticket:
        return None
    with _lock:
        entry = _tickets.pop(ticket, None)
    if not entry or entry["purpose"] != purpose or entry["expires_at"] < time.time():
        return None
    return entry["token"] if get_session(entry["token"]) else None
