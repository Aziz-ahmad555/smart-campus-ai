import asyncio
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv
from backend.tracking import engine

load_dotenv()

app = FastAPI(title="Smart Campus AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
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

@app.get("/events")
def get_events():
    with engine.events_lock:
        return {"events": list(engine.events_log)}

def mjpeg_generator():
    while True:
        frame = engine.get_latest_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.05)

@app.get("/video-feed")
def video_feed():
    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    engine.connected_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        engine.connected_websockets.remove(websocket)

# ---- Student CRUD ----

@app.get("/students")
def list_students():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT s.id, s.name, s.roll_number, s.photo_folder, s.created_at, s.class_id, c.name AS class_name FROM students s LEFT JOIN classes c ON s.class_id = c.id ORDER BY s.id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"students": rows}

@app.post("/students")
def create_student(student: StudentCreate, token: str):
    require_admin(token)
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
def update_student(student_id: int, student: StudentUpdate, token: str):
    require_admin(token)
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
def delete_student(student_id: int, token: str):
    require_admin(token)
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

# ---- Visitor Management ----

def compute_visitor_status(row):
    if row["check_out_time"] is not None:
        return "checked_out"
    expiry = row["check_in_time"] + timedelta(minutes=row["allowed_minutes"])
    if datetime.now() > expiry:
        return "overstayed"
    return "checked_in"

@app.get("/visitors")
def list_visitors():
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
def check_in_visitor(visitor: VisitorCreate, token: str):
    require_admin(token)
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
def check_out_visitor(visitor_id: int, token: str):
    require_admin(token)
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
def delete_visitor(visitor_id: int, token: str):
    require_admin(token)
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

# ---- Classes ----

class ClassCreate(BaseModel):
    name: str
    grade_level: Optional[str] = None
    section: Optional[str] = None

@app.get("/classes")
def list_classes():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM classes ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"classes": rows}

@app.post("/classes")
def create_class(cls: ClassCreate, token: str):
    require_admin(token)
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
def delete_class(class_id: int, token: str):
    require_admin(token)
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

# ---- Staff ----

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
def list_staff():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM staff ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"staff": rows}

@app.post("/staff")
def create_staff(person: StaffCreate, token: str):
    require_admin(token)
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
def update_staff(staff_id: int, person: StaffUpdate, token: str):
    require_admin(token)
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
def delete_staff(staff_id: int, token: str):
    require_admin(token)
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

import bcrypt
import secrets

active_sessions = {}  # token -> {user_id, username, role, full_name}

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

    token = secrets.token_hex(32)
    active_sessions[token] = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user["full_name"],
    }

    return {
        "token": token,
        "user": {
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"],
        }
    }

@app.get("/me")
def get_current_user(token: str):
    session = active_sessions.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return {"user": session}

@app.post("/logout")
def logout(token: str):
    active_sessions.pop(token, None)
    return {"logged_out": True}

# ---- Teacher class roster ----

@app.get("/my-class-roster")
def get_class_roster(teacher_name: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT class_id FROM staff WHERE name = %s;", (teacher_name,))
    teacher_row = cur.fetchone()

    if not teacher_row or not teacher_row["class_id"]:
        cur.close()
        conn.close()
        return {"class_name": None, "students": []}

    class_id = teacher_row["class_id"]

    cur.execute("SELECT name FROM classes WHERE id = %s;", (class_id,))
    class_row = cur.fetchone()

    cur.execute("SELECT id, name, roll_number, photo_folder FROM students WHERE class_id = %s ORDER BY name;", (class_id,))
    students = cur.fetchall()

    cur.close()
    conn.close()

    return {"class_name": class_row["name"] if class_row else None, "students": students}

# ---- Secure, session-derived personal views ----

def require_session(token: str):
    session = active_sessions.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session

@app.get("/secure/my-events")
def secure_my_events(token: str):
    session = require_session(token)
    full_name = session["full_name"]

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.close()
    conn.close()

    with engine.events_lock:
        all_events = list(engine.events_log)

    my_events = [e for e in all_events if e.get("label") and full_name in e["label"]]
    return {"events": my_events}

@app.get("/secure/my-class-roster")
def secure_my_class_roster(token: str):
    session = require_session(token)
    if session["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can access this endpoint")

    full_name = session["full_name"]

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT class_id FROM staff WHERE name = %s;", (full_name,))
    teacher_row = cur.fetchone()

    if not teacher_row or not teacher_row["class_id"]:
        cur.close()
        conn.close()
        return {"class_name": None, "students": []}

    class_id = teacher_row["class_id"]

    cur.execute("SELECT name FROM classes WHERE id = %s;", (class_id,))
    class_row = cur.fetchone()

    cur.execute("SELECT id, name, roll_number, photo_folder FROM students WHERE class_id = %s ORDER BY name;", (class_id,))
    students = cur.fetchall()

    cur.close()
    conn.close()

    student_names = [s["name"] for s in students]
    with engine.events_lock:
        all_events = list(engine.events_log)
    class_events = [e for e in all_events if e.get("label") and any(name in e["label"] for name in student_names)]

    return {"class_name": class_row["name"] if class_row else None, "students": students, "events": class_events}

def require_admin(token: str):
    session = active_sessions.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    if session["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return session











