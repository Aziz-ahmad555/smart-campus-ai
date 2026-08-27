import os
import cv2
import time
import threading
import asyncio
import psycopg2
from dotenv import load_dotenv
from deepface import DeepFace
from ultralytics import YOLO

load_dotenv()

KNOWN_FACES_DB = "data/known_faces"
EXIT_TIMEOUT_SECONDS = 5

person_model = YOLO("yolov8n.pt")
known_track_ids = {}
events_log = []
events_lock = threading.Lock()

# WebSocket broadcasting support
connected_websockets = []
main_event_loop = None  # set by FastAPI on startup

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def lookup_student(photo_folder):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT name, roll_number FROM students WHERE photo_folder = %s;",
            (photo_folder,)
        )
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            name, roll_number = result
            return f"{name} ({roll_number})"
        return None
    except Exception as e:
        print("DB lookup error:", e)
        return None

def recognize_face_in_crop(crop):
    try:
        results = DeepFace.find(
            img_path=crop,
            db_path=KNOWN_FACES_DB,
            enforce_detection=False,
            silent=True,
            detector_backend="opencv"
        )
        if len(results) > 0 and len(results[0]) > 0:
            best_match_path = results[0].iloc[0]["identity"]
            photo_folder = os.path.basename(os.path.dirname(best_match_path))
            return photo_folder
        return None
    except Exception:
        return None

def broadcast_event(event):
    """Send event to all connected WebSocket clients (thread-safe)."""
    if main_event_loop is None:
        return
    for ws in list(connected_websockets):
        asyncio.run_coroutine_threadsafe(safe_send(ws, event), main_event_loop)

async def safe_send(ws, event):
    try:
        await ws.send_json(event)
    except Exception:
        if ws in connected_websockets:
            connected_websockets.remove(ws)

def add_event(event_type, track_id, label):
    event = {
        "type": event_type,
        "track_id": int(track_id),
        "label": label,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with events_lock:
        events_log.append(event)
        if len(events_log) > 100:
            events_log.pop(0)
    broadcast_event(event)

def run_tracking_loop():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("Background tracking loop started.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = person_model.track(frame, classes=[0], persist=True, verbose=False)
        current_frame_ids = set()

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)

            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = map(int, box)
                current_frame_ids.add(track_id)

                if track_id not in known_track_ids:
                    person_crop = frame[max(0,y1):y2, max(0,x1):x2]
                    photo_folder = recognize_face_in_crop(person_crop)

                    if photo_folder:
                        student_info = lookup_student(photo_folder)
                        label = student_info if student_info else photo_folder
                    else:
                        label = "Unknown"

                    known_track_ids[track_id] = {
                        "label": label,
                        "entry_time": time.time(),
                        "last_seen": time.time()
                    }
                    add_event("ENTRY", track_id, label)
                    print(f"[ENTRY] Track ID {track_id}: {label}")
                else:
                    known_track_ids[track_id]["last_seen"] = time.time()

        now = time.time()
        exited_ids = []
        for track_id, info in known_track_ids.items():
            if track_id not in current_frame_ids and (now - info["last_seen"]) > EXIT_TIMEOUT_SECONDS:
                exited_ids.append(track_id)

        for track_id in exited_ids:
            label = known_track_ids[track_id]["label"]
            add_event("EXIT", track_id, label)
            print(f"[EXIT] Track ID {track_id}: {label}")
            del known_track_ids[track_id]

    cap.release()

def start_background_tracking():
    thread = threading.Thread(target=run_tracking_loop, daemon=True)
    thread.start()
