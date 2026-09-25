import asyncio
import base64
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

from backend.api import auth, conflicts, users
from backend.api.auth import admin_only, current_session, teacher_only
from backend.api.db import get_db_connection
from backend.tracking import engine, event_store

# Where the dashboard is served from (CORS and WebAuthn). Set in .env.
FRONTEND_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if o.strip()]
if not FRONTEND_ORIGINS or any("*" in o for o in FRONTEND_ORIGINS):
    raise RuntimeError("FRONTEND_ORIGIN must list the dashboard's exact origin(s); '*' is not allowed.")

app = FastAPI(title="Smart Campus AI API")
# Any foreign-key refusal an endpoint doesn't handle itself becomes a 409.
app.add_exception_handler(psycopg2.errors.ForeignKeyViolation, conflicts.unhandled_fk_violation)
app.include_router(users.router)          # /users: admin account management

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,          # never "*"
    allow_credentials=False,                 # auth is a Bearer header, not cookies
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    response.headers.setdefault("Cache-Control", "no-store")     # API data is personal; don't cache it
    return response


# Text limits match the database columns (VARCHAR(n)), so over-long input is
# rejected with 422 before it reaches the database.
class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    roll_number: str = Field(min_length=1, max_length=50)
    photo_folder: str = Field(min_length=1, max_length=100)
    class_id: Optional[int] = None


class StudentUpdate(StudentCreate):
    pass


class VisitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cnic_or_id: Optional[str] = Field(None, max_length=50)
    reason: Optional[str] = Field(None, max_length=255)
    host_name: Optional[str] = Field(None, max_length=100)
    allowed_minutes: int = Field(60, gt=0, le=1440)   # 1 minute to 24 hours


@app.on_event("startup")
def startup_event():
    engine.main_event_loop = asyncio.get_event_loop()
    engine.start_background_tracking()


@app.on_event("shutdown")
def shutdown_event():
    event_store.stop()          # write out any queued events before exiting


# Pagination for event history: newest first, `before` = the last id you got.
def page_params(limit: int = Query(100, ge=1, le=200), before: Optional[int] = Query(None, ge=1)):
    return {"limit": limit, "before": before}


@app.get("/")
def read_root():
    return {"message": "Smart Campus AI backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---- Live pipeline: events, camera feed, WebSocket (admin) ----

@app.get("/events")
def get_events(session=Depends(admin_only), page=Depends(page_params)):
    """All recognition events from the database, newest first."""
    events, next_before = event_store.query_events(**page)
    return {"events": events, "next_before": next_before}


@app.post("/stream-ticket")
def stream_ticket(purpose: str, session=Depends(admin_only)):
    """Short-lived ticket for /video-feed or /ws/events (see auth.py)."""
    return {"ticket": auth.issue_ticket(session["token"], purpose), "expires_in": auth.TICKET_TTL_SECONDS}


def mjpeg_generator(token):
    while auth.get_session(token):          # the stream ends when the session does
        frame = engine.get_latest_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.05)


@app.get("/video-feed")
def video_feed(ticket: str = None):
    token = auth.redeem_ticket(ticket, "video")
    if not token:
        raise HTTPException(status_code=401, detail="Missing, expired or used stream ticket")
    return StreamingResponse(
        mjpeg_generator(token),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, ticket: str = None):
    token = auth.redeem_ticket(ticket, "events")
    if not token:
        await websocket.close(code=4401)    # before accept: the handshake is refused
        return
    await websocket.accept()
    engine.connected_websockets.append(websocket)
    try:
        while auth.get_session(token):
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                pass
        await websocket.close(code=4401)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in engine.connected_websockets:
            engine.connected_websockets.remove(websocket)


# ---- Student CRUD (admin) ----

@app.get("/students")
def list_students(session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT s.id, s.name, s.roll_number, s.photo_folder, s.created_at, s.class_id, c.name AS class_name FROM students s LEFT JOIN classes c ON s.class_id = c.id ORDER BY s.id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"students": rows}


@app.post("/students")
def create_student(student: StudentCreate, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "INSERT INTO students (name, roll_number, photo_folder, class_id) VALUES (%s, %s, %s, %s) RETURNING id, name, roll_number, photo_folder, created_at, class_id;",
            (student.name, student.roll_number, student.photo_folder, student.class_id)
        )
        new_student = cur.fetchone()
        conn.commit()
        return {"student": new_student}
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Roll number already exists")
    except psycopg2.errors.ForeignKeyViolation as e:
        raise conflicts.conflict(e, conn)
    finally:
        cur.close()
        conn.close()


@app.put("/students/{student_id}")
def update_student(student_id: int, student: StudentUpdate, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "UPDATE students SET name = %s, roll_number = %s, photo_folder = %s, class_id = %s WHERE id = %s RETURNING id, name, roll_number, photo_folder, created_at, class_id;",
            (student.name, student.roll_number, student.photo_folder, student.class_id, student_id)
        )
        updated = cur.fetchone()
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Roll number already exists")
    except psycopg2.errors.ForeignKeyViolation as e:
        raise conflicts.conflict(e, conn)
    finally:
        cur.close()
        conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"student": updated}


@app.delete("/students/{student_id}")
def delete_student(student_id: int, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM students WHERE id = %s RETURNING id;", (student_id,))
        deleted = cur.fetchone()
        conn.commit()
    except psycopg2.errors.ForeignKeyViolation as e:     # still referenced: say what to fix
        raise conflicts.conflict(e, conn, deleting=("students", student_id))
    finally:
        cur.close()
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"deleted": True}


# ---- Visitor Management (admin) ----

def compute_visitor_status(row):
    if row["check_out_time"] is not None:
        return "checked_out"
    expiry = row["check_in_time"] + timedelta(minutes=row["allowed_minutes"])
    if datetime.now() > expiry:
        return "overstayed"
    return "checked_in"


@app.get("/visitors")
def list_visitors(session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM visitors ORDER BY check_in_time DESC;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    for row in rows:
        row["status"] = compute_visitor_status(row)
        row["expiry_time"] = row["check_in_time"] + timedelta(minutes=row["allowed_minutes"])
    return {"visitors": rows}


@app.post("/visitors")
def check_in_visitor(visitor: VisitorCreate, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "INSERT INTO visitors (name, cnic_or_id, reason, host_name, allowed_minutes) VALUES (%s, %s, %s, %s, %s) RETURNING *;",
        (visitor.name, visitor.cnic_or_id, visitor.reason, visitor.host_name, visitor.allowed_minutes)
    )
    new_visitor = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"visitor": new_visitor}


@app.put("/visitors/{visitor_id}/checkout")
def check_out_visitor(visitor_id: int, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "UPDATE visitors SET check_out_time = CURRENT_TIMESTAMP, status = 'checked_out' WHERE id = %s RETURNING *;",
        (visitor_id,)
    )
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return {"visitor": updated}


@app.delete("/visitors/{visitor_id}")
def delete_visitor(visitor_id: int, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM visitors WHERE id = %s RETURNING id;", (visitor_id,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return {"deleted": True}


# ---- Classes (admin) ----

class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    grade_level: Optional[str] = Field(None, max_length=20)
    section: Optional[str] = Field(None, max_length=10)


@app.get("/classes")
def list_classes(session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM classes ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"classes": rows}


@app.post("/classes")
def create_class(cls: ClassCreate, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "INSERT INTO classes (name, grade_level, section) VALUES (%s, %s, %s) RETURNING *;",
        (cls.name, cls.grade_level, cls.section)
    )
    new_class = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"class": new_class}


@app.delete("/classes/{class_id}")
def delete_class(class_id: int, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM classes WHERE id = %s RETURNING id;", (class_id,))
        deleted = cur.fetchone()
        conn.commit()
    except psycopg2.errors.ForeignKeyViolation as e:     # still referenced: say what to fix
        raise conflicts.conflict(e, conn, deleting=("classes", class_id))
    finally:
        cur.close()
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Class not found")
    return {"deleted": True}


# ---- Staff (admin) ----

class StaffCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    photo_folder: str = Field(min_length=1, max_length=100)


class StaffUpdate(StaffCreate):
    pass


@app.get("/staff")
def list_staff(session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM staff ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"staff": rows}


@app.post("/staff")
def create_staff(person: StaffCreate, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "INSERT INTO staff (name, role, department, photo_folder) VALUES (%s, %s, %s, %s) RETURNING *;",
        (person.name, person.role, person.department, person.photo_folder)
    )
    new_staff = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return {"staff": new_staff}


@app.put("/staff/{staff_id}")
def update_staff(staff_id: int, person: StaffUpdate, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "UPDATE staff SET name = %s, role = %s, department = %s, photo_folder = %s WHERE id = %s RETURNING *;",
        (person.name, person.role, person.department, person.photo_folder, staff_id)
    )
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"staff": updated}


@app.delete("/staff/{staff_id}")
def delete_staff(staff_id: int, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM staff WHERE id = %s RETURNING id;", (staff_id,))
        deleted = cur.fetchone()
        conn.commit()
    except psycopg2.errors.ForeignKeyViolation as e:     # still referenced: say what to fix
        raise conflicts.conflict(e, conn, deleting=("staff", staff_id))
    finally:
        cur.close()
        conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"deleted": True}


# ---- Authentication ----

class LoginRequest(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=256)


# Checked when the username doesn't exist, so unknown and known usernames
# take the same time to reject (no username discovery by timing).
_DUMMY_HASH = bcrypt.hashpw(b"no-such-user", bcrypt.gensalt()).decode()


def password_matches(password, password_hash):
    raw = password.encode("utf-8")
    if len(raw) > 72:          # bcrypt's limit: no stored password can be longer
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except ValueError:         # malformed stored hash
        return False


def client_ip(request):
    return request.client.host if request.client else "unknown"


@app.post("/login")
def login(credentials: LoginRequest, request: Request):
    ip = client_ip(request)
    auth.check_login_allowed(credentials.username, ip)          # 429 while locked out

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE username = %s;", (credentials.username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    ok = password_matches(credentials.password, user["password_hash"] if user else _DUMMY_HASH)
    if not (user and ok):
        auth.login_limiter.failed(credentials.username, ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    auth.login_limiter.succeeded(credentials.username)
    token = auth.create_session(user)
    session = auth.get_session(token)
    return {"token": token, "expires_at": auth.session_expiry(session), "user": auth.public_user(session)}


@app.get("/me")
def get_current_user(session=Depends(current_session)):
    return {"user": auth.public_user(session), "expires_at": auth.session_expiry(session)}


@app.post("/logout")
def logout(session=Depends(current_session)):
    auth.end_session(session["token"])
    return {"logged_out": True}


# ---- Teacher class roster (teacher; derived from the session) ----

def teacher_class(cur, staff_id):
    """The class taught by the staff member linked to this account (users.staff_id)."""
    if not staff_id:
        return None, None, []
    cur.execute("SELECT class_id FROM staff WHERE id = %s;", (staff_id,))
    teacher_row = cur.fetchone()
    if not teacher_row or not teacher_row["class_id"]:
        return None, None, []
    class_id = teacher_row["class_id"]
    cur.execute("SELECT name FROM classes WHERE id = %s;", (class_id,))
    class_row = cur.fetchone()
    cur.execute("SELECT id, name, roll_number, photo_folder FROM students WHERE class_id = %s ORDER BY name;", (class_id,))
    return class_id, (class_row["name"] if class_row else None), cur.fetchall()


@app.get("/my-class-roster")
def get_class_roster(session=Depends(teacher_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    _, class_name, students = teacher_class(cur, session["staff_id"])
    cur.close()
    conn.close()
    return {"class_name": class_name, "students": students}


# ---- Secure, session-derived personal views ----

@app.get("/secure/my-events")
def secure_my_events(session=Depends(current_session), page=Depends(page_params)):
    """The signed-in person's own events (matched by ID), newest first.
    `linked` is false when the account isn't linked to a student or staff
    record yet."""
    if session["student_id"]:
        events, next_before = event_store.query_events("student_id = %s", [session["student_id"]], **page)
    elif session["staff_id"]:
        events, next_before = event_store.query_events("staff_id = %s", [session["staff_id"]], **page)
    else:
        return {"events": [], "next_before": None, "linked": False}
    return {"events": events, "next_before": next_before, "linked": True}


@app.get("/secure/my-class-roster")
def secure_my_class_roster(session=Depends(teacher_only), page=Depends(page_params)):
    """The teacher's class roster and its students' events (by ID), newest first."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    _, class_name, students = teacher_class(cur, session["staff_id"])
    cur.close()
    conn.close()

    ids = [s["id"] for s in students]
    events, next_before = event_store.query_events("student_id = ANY(%s)", [ids], **page) if ids else ([], None)
    return {"class_name": class_name, "students": students, "events": events,
            "next_before": next_before, "linked": bool(session["staff_id"])}


# ---- WebAuthn Fingerprint Authentication ----

# WebAuthn: the relying-party ID is the dashboard's domain (no scheme/port),
# and the expected origin is where the dashboard is served from.
RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
RP_NAME = "Sentra Campus Intelligence"
ORIGIN = FRONTEND_ORIGINS[0]

CHALLENGE_TTL_SECONDS = 120
_challenges = {}   # key -> (challenge bytes, username or None, expires_at)


def store_challenge(key, challenge, username=None):
    now = time.time()
    for k in [k for k, v in _challenges.items() if v[2] < now]:
        del _challenges[k]
    _challenges[key] = (challenge, username, now + CHALLENGE_TTL_SECONDS)


def take_challenge(key):
    """Single use: returns (challenge, username) once, if not expired."""
    entry = _challenges.pop(key, None)
    if not entry or entry[2] < time.time():
        return None, None
    return entry[0], entry[1]


def b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


@app.post("/webauthn/register/begin")
def webauthn_register_begin(session=Depends(current_session)):
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=str(session["user_id"]).encode("utf-8"),
        user_name=session["username"],
        user_display_name=session["full_name"] or session["username"],
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    store_challenge("register:" + session["token"], options.challenge)
    return {"options": options_to_json(options)}


class RegisterCompleteRequest(BaseModel):
    credential: dict


@app.post("/webauthn/register/complete")
def webauthn_register_complete(body: RegisterCompleteRequest, session=Depends(current_session)):
    expected_challenge, _ = take_challenge("register:" + session["token"])
    if not expected_challenge:
        raise HTTPException(status_code=400, detail="The fingerprint setup request expired. Please try again.")

    try:
        verification = verify_registration_response(
            credential=body.credential,
            expected_challenge=expected_challenge,
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
        )
    except Exception as e:
        print(f"[webauthn] registration rejected for user #{session['user_id']}: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="Fingerprint setup could not be verified. Please try again.")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO webauthn_credentials (user_id, credential_id, public_key, sign_count) VALUES (%s, %s, %s, %s);",
            (session["user_id"], verification.credential_id, verification.credential_public_key, verification.sign_count)
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="This fingerprint is already registered.")
    finally:
        cur.close()
        conn.close()
    return {"registered": True}


NOT_SET_UP = "Fingerprint sign-in isn't set up for this account."


@app.post("/webauthn/login/begin")
def webauthn_login_begin(username: str = Query(max_length=50)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT c.credential_id FROM webauthn_credentials c JOIN users u ON u.id = c.user_id WHERE u.username = %s;",
        (username,),
    )
    creds = cur.fetchall()
    cur.close()
    conn.close()

    # Same answer for an unknown user and a user without fingerprints, so
    # this can't be used to find out which usernames exist.
    if not creds:
        raise HTTPException(status_code=400, detail=NOT_SET_UP)

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=[PublicKeyCredentialDescriptor(id=bytes(c["credential_id"])) for c in creds],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    # A random id per attempt: nobody can replace someone else's pending challenge.
    challenge_id = secrets.token_urlsafe(24)
    store_challenge("login:" + challenge_id, options.challenge, username)
    return {"options": options_to_json(options), "challenge_id": challenge_id}


class LoginCompleteRequest(BaseModel):
    username: str = Field(max_length=50)
    challenge_id: str = Field(max_length=64)
    credential: dict


@app.post("/webauthn/login/complete")
def webauthn_login_complete(body: LoginCompleteRequest, request: Request):
    ip = client_ip(request)
    auth.check_login_allowed(body.username, ip)

    expected_challenge, challenged_user = take_challenge("login:" + body.challenge_id)
    if not expected_challenge or challenged_user != body.username:
        raise HTTPException(status_code=400, detail="The sign-in request expired. Please try again.")

    try:
        cred_id_bytes = b64_decode(str(body.credential["rawId"]))
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid fingerprint response.")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE username = %s;", (body.username,))
    user = cur.fetchone()
    stored_cred = None
    if user:
        # The credential must belong to THIS account: a valid fingerprint
        # registered to someone else must never sign in as this user.
        cur.execute("SELECT * FROM webauthn_credentials WHERE credential_id = %s AND user_id = %s;",
                    (cred_id_bytes, user["id"]))
        stored_cred = cur.fetchone()
    cur.close()
    conn.close()

    if not stored_cred:
        auth.login_limiter.failed(body.username, ip)
        raise HTTPException(status_code=401, detail="Fingerprint not recognized for this account.")

    try:
        verification = verify_authentication_response(
            credential=body.credential,
            expected_challenge=expected_challenge,
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
            credential_public_key=bytes(stored_cred["public_key"]),
            credential_current_sign_count=stored_cred["sign_count"],
        )
    except Exception as e:
        auth.login_limiter.failed(body.username, ip)
        print(f"[webauthn] sign-in rejected for user #{user['id']}: {type(e).__name__}")
        raise HTTPException(status_code=401, detail="Fingerprint sign-in failed.")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE webauthn_credentials SET sign_count = %s WHERE id = %s;", (verification.new_sign_count, stored_cred["id"]))
    conn.commit()
    cur.close()
    conn.close()

    auth.login_limiter.succeeded(body.username)
    token = auth.create_session(user)
    session = auth.get_session(token)
    return {"token": token, "expires_at": auth.session_expiry(session), "user": auth.public_user(session)}
