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

class StudentUpdate(BaseModel):
    name: str
    roll_number: str
    photo_folder: str

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
    cur.execute("SELECT id, name, roll_number, photo_folder, created_at FROM students ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"students": rows}

@app.post("/students")
def create_student(student: StudentCreate):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "INSERT INTO students (name, roll_number, photo_folder) VALUES (%s, %s, %s) RETURNING id, name, roll_number, photo_folder, created_at;",
            (student.name, student.roll_number, student.photo_folder)
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
def update_student(student_id: int, student: StudentUpdate):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "UPDATE students SET name = %s, roll_number = %s, photo_folder = %s WHERE id = %s RETURNING id, name, roll_number, photo_folder, created_at;",
        (student.name, student.roll_number, student.photo_folder, student_id)
    )
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not updated:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"student": updated}

@app.delete("/students/{student_id}")
def delete_student(student_id: int):
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
def check_in_visitor(visitor: VisitorCreate):
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
def check_out_visitor(visitor_id: int):
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
def delete_visitor(visitor_id: int):
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
