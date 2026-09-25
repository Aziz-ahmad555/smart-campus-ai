import asyncio
import base64
import time
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
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

from backend.api import auth
from backend.api.auth import admin_only, current_session, teacher_only
from backend.api.db import get_db_connection
from backend.tracking import engine

app = FastAPI(title="Smart Campus AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StudentCreate(BaseModel):
    name: str
    roll_number: str
    photo_folder: str
    class_id: Optional[int] = None


class StudentUpdate(BaseModel):
    name: str
    roll_number: str
    photo_folder: str
    class_id: Optional[int] = None


class VisitorCreate(BaseModel):
    name: str
    cnic_or_id: Optional[str] = None
    reason: Optional[str] = None
    host_name: Optional[str] = None
    allowed_minutes: int = 60


@app.on_event("startup")
def startup_event():
    engine.main_event_loop = asyncio.get_event_loop()
    engine.start_background_tracking()


@app.get("/")
def read_root():
    return {"message": "Smart Campus AI backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---- Live pipeline: events, camera feed, WebSocket (admin) ----

@app.get("/events")
def get_events(session=Depends(admin_only)):
    with engine.events_lock:
        return {"events": list(engine.events_log)}


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
    finally:
        cur.close()
        conn.close()


@app.put("/students/{student_id}")
def update_student(student_id: int, student: StudentUpdate, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "UPDATE students SET name = %s, roll_number = %s, photo_folder = %s, class_id = %s WHERE id = %s RETURNING id, name, roll_number, photo_folder, created_at, class_id;",
        (student.name, student.roll_number, student.photo_folder, student.class_id, student_id)
    )
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"student": updated}


@app.delete("/students/{student_id}")
def delete_student(student_id: int, session=Depends(admin_only)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE id = %s RETURNING id;", (student_id,))
    deleted = cur.fetchone()
    conn.commit()
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
    name: str
    grade_level: Optional[str] = None
    section: Optional[str] = None


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
    cur.execute("DELETE FROM classes WHERE id = %s RETURNING id;", (class_id,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Class not found")
    return {"deleted": True}


# ---- Staff (admin) ----

class StaffCreate(BaseModel):
    name: str
    role: str
    department: Optional[str] = None
    photo_folder: str


class StaffUpdate(BaseModel):
    name: str
    role: str
    department: Optional[str] = None
    photo_folder: str


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
    cur.execute("DELETE FROM staff WHERE id = %s RETURNING id;", (staff_id,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return {"deleted": True}


# ---- Authentication ----

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/login")
def login(credentials: LoginRequest):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE username = %s;", (credentials.username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not bcrypt.checkpw(credentials.password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid username or password")

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

def teacher_class(cur, full_name):
    cur.execute("SELECT class_id FROM staff WHERE name = %s;", (full_name,))
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
    _, class_name, students = teacher_class(cur, session["full_name"])
    cur.close()
    conn.close()
    return {"class_name": class_name, "students": students}


# ---- Secure, session-derived personal views ----

@app.get("/secure/my-events")
def secure_my_events(session=Depends(current_session)):
    full_name = session["full_name"]
    with engine.events_lock:
        all_events = list(engine.events_log)
    my_events = [e for e in all_events if e.get("label") and full_name in e["label"]]
    return {"events": my_events}


@app.get("/secure/my-class-roster")
def secure_my_class_roster(session=Depends(teacher_only)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    _, class_name, students = teacher_class(cur, session["full_name"])
    cur.close()
    conn.close()

    student_names = [s["name"] for s in students]
    with engine.events_lock:
        all_events = list(engine.events_log)
    class_events = [e for e in all_events if e.get("label") and any(name in e["label"] for name in student_names)]

    return {"class_name": class_name, "students": students, "events": class_events}


# ---- WebAuthn Fingerprint Authentication ----

RP_ID = "localhost"
RP_NAME = "Sentra Campus Intelligence"
ORIGIN = "http://localhost:5173"

webauthn_challenges = {}  # temporary storage: token -> challenge bytes


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

    webauthn_challenges[session["token"]] = options.challenge
    return {"options": options_to_json(options)}


class RegisterCompleteRequest(BaseModel):
    credential: dict


@app.post("/webauthn/register/complete")
def webauthn_register_complete(body: RegisterCompleteRequest, session=Depends(current_session)):
    expected_challenge = webauthn_challenges.get(session["token"])
    if not expected_challenge:
        raise HTTPException(status_code=400, detail="No pending registration challenge")

    try:
        verification = verify_registration_response(
            credential=body.credential,
            expected_challenge=expected_challenge,
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration verification failed: {e}")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO webauthn_credentials (user_id, credential_id, public_key, sign_count) VALUES (%s, %s, %s, %s);",
        (session["user_id"], verification.credential_id, verification.credential_public_key, verification.sign_count)
    )
    conn.commit()
    cur.close()
    conn.close()

    webauthn_challenges.pop(session["token"], None)
    return {"registered": True}


@app.post("/webauthn/login/begin")
def webauthn_login_begin(username: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
    user = cur.fetchone()
    if not user:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    cur.execute("SELECT credential_id FROM webauthn_credentials WHERE user_id = %s;", (user["id"],))
    creds = cur.fetchall()
    cur.close()
    conn.close()

    if not creds:
        raise HTTPException(status_code=400, detail="No fingerprint registered for this user")

    allow_credentials = [
        PublicKeyCredentialDescriptor(id=bytes(c["credential_id"])) for c in creds
    ]

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    login_challenge_key = "login_" + username
    webauthn_challenges[login_challenge_key] = options.challenge
    return {"options": options_to_json(options)}


class LoginCompleteRequest(BaseModel):
    username: str
    credential: dict


@app.post("/webauthn/login/complete")
def webauthn_login_complete(body: LoginCompleteRequest):
    login_challenge_key = "login_" + body.username
    expected_challenge = webauthn_challenges.get(login_challenge_key)
    if not expected_challenge:
        raise HTTPException(status_code=400, detail="No pending login challenge")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE username = %s;", (body.username,))
    user = cur.fetchone()

    cred_id_bytes = b64_decode(body.credential["rawId"])
    cur.execute("SELECT * FROM webauthn_credentials WHERE credential_id = %s;", (cred_id_bytes,))
    stored_cred = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not stored_cred:
        raise HTTPException(status_code=400, detail="Credential not recognized")

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
        raise HTTPException(status_code=400, detail=f"Authentication failed: {e}")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE webauthn_credentials SET sign_count = %s WHERE id = %s;", (verification.new_sign_count, stored_cred["id"]))
    conn.commit()
    cur.close()
    conn.close()

    token = auth.create_session(user)
    webauthn_challenges.pop(login_challenge_key, None)
    session = auth.get_session(token)
    return {"token": token, "expires_at": auth.session_expiry(session), "user": auth.public_user(session)}
