import os
import cv2
import time
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
import psycopg2
from dotenv import load_dotenv
from deepface import DeepFace
from ultralytics import YOLO

load_dotenv()

KNOWN_FACES_DB = "data/known_faces"
EXIT_TIMEOUT_SECONDS = 5
CROWD_THRESHOLD = 3
CROWD_ALERT_COOLDOWN = 10

person_model = YOLO("yolov8n.pt")
face_model = YOLO("backend/detection/models/yolov8n-face.pt")

known_track_ids = {}  # track_id -> {label, entry_time, last_seen, status}
events_log = []
events_lock = threading.Lock()

connected_websockets = []
main_event_loop = None

last_crowd_alert_time = 0
current_person_count = 0

latest_frame = None
frame_lock = threading.Lock()

recognition_executor = ThreadPoolExecutor(max_workers=2)
recognition_in_progress = set()
recognition_results_lock = threading.Lock()

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

def get_tight_face_crop(person_crop):
    """Run face detection WITHIN the person crop to isolate just the face region."""
    if person_crop.size == 0:
        return None
    try:
        face_results = face_model(person_crop, verbose=False)
        boxes = face_results[0].boxes.xyxy.cpu().numpy()
        if len(boxes) == 0:
            return None
        # Take the largest face box (most prominent face in this person's crop)
        areas = [(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]
        best_box = boxes[areas.index(max(areas))]
        fx1, fy1, fx2, fy2 = map(int, best_box)
        face_crop = person_crop[max(0,fy1):fy2, max(0,fx1):fx2]
        if face_crop.size == 0:
            return None
        return face_crop
    except Exception:
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
        "track_id": int(track_id) if track_id is not None else None,
        "label": label,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with events_lock:
        events_log.append(event)
        if len(events_log) > 100:
            events_log.pop(0)
    broadcast_event(event)

def check_crowd(person_count):
    global last_crowd_alert_time
    now = time.time()
    if person_count >= CROWD_THRESHOLD and (now - last_crowd_alert_time) > CROWD_ALERT_COOLDOWN:
        last_crowd_alert_time = now
        add_event("CROWD_ALERT", None, f"{person_count} people detected in frame")
        print(f"[CROWD ALERT] {person_count} people detected at {time.strftime('%H:%M:%S')}")

def run_recognition_async(track_id, person_crop):
    """Runs in a background thread — does NOT block the video loop."""
    try:
        face_crop = get_tight_face_crop(person_crop)
        target = face_crop if face_crop is not None else person_crop

        photo_folder = recognize_face_in_crop(target)
        if photo_folder:
            student_info = lookup_student(photo_folder)
            label = student_info if student_info else photo_folder
        else:
            label = "Unknown"

        if track_id in known_track_ids:
            known_track_ids[track_id]["label"] = label
            known_track_ids[track_id]["status"] = "done"
            add_event("ENTRY", track_id, label)
            print(f"[ENTRY] Track ID {track_id}: {label}")
    finally:
        with recognition_results_lock:
            recognition_in_progress.discard(track_id)

def update_latest_frame(frame):
    global latest_frame
    ok, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if ok:
        with frame_lock:
            latest_frame = buffer.tobytes()

def get_latest_frame():
    with frame_lock:
        return latest_frame

def run_tracking_loop():
    global current_person_count
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
            current_person_count = len(track_ids)

            check_crowd(current_person_count)

            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = map(int, box)
                current_frame_ids.add(track_id)

                if track_id not in known_track_ids:
                    known_track_ids[track_id] = {
                        "label": "Identifying...",
                        "entry_time": time.time(),
                        "last_seen": time.time(),
                        "status": "pending"
                    }
                    with recognition_results_lock:
                        if track_id not in recognition_in_progress:
                            recognition_in_progress.add(track_id)
                            person_crop = frame[max(0,y1):y2, max(0,x1):x2].copy()
                            recognition_executor.submit(run_recognition_async, track_id, person_crop)
                else:
                    known_track_ids[track_id]["last_seen"] = time.time()

                label_text = known_track_ids[track_id]["label"]
                box_color = (0, 200, 0) if label_text not in ("Unknown", "Identifying...") else \
                            (0, 165, 255) if label_text == "Identifying..." else (0, 0, 220)
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                cv2.putText(frame, f"ID {track_id}: {label_text}", (x1, max(y1-10, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 2)
        else:
            current_person_count = 0

        now = time.time()
        exited_ids = []
        for track_id, info in known_track_ids.items():
            if track_id not in current_frame_ids and (now - info["last_seen"]) > EXIT_TIMEOUT_SECONDS:
                exited_ids.append(track_id)

        for track_id in exited_ids:
            label = known_track_ids[track_id]["label"]
            if label != "Identifying...":
                add_event("EXIT", track_id, label)
                print(f"[EXIT] Track ID {track_id}: {label}")
            del known_track_ids[track_id]

        update_latest_frame(frame)

    cap.release()

def start_background_tracking():
    thread = threading.Thread(target=run_tracking_loop, daemon=True)
    thread.start()
