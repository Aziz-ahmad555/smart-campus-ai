import asyncio
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
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

# ---- Student CRUD endpoints ----

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
