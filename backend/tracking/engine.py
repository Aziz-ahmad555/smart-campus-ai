import os
import cv2
import time
import threading
import asyncio
import numpy as np
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
import psycopg2
from dotenv import load_dotenv
from deepface import DeepFace
from ultralytics import YOLO

from backend.tracking import event_store

load_dotenv()

KNOWN_FACES_DB = "data/known_faces"
# Webcam index ("0") or a stream URL (e.g. rtsp://...), from CAMERA_SOURCE in .env.
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "0")
EXIT_TIMEOUT_SECONDS = 5
CROWD_THRESHOLD = 3
CROWD_ALERT_COOLDOWN = 10
FACE_DETECTION_MIN_CONFIDENCE = 0.55
MATCH_SIMILARITY_THRESHOLD = 0.62
VOTE_SAMPLE_COUNT = 3
VOTE_SAMPLE_INTERVAL = 0.35

# Fall detection tuning
FALL_RATIO_HISTORY_LEN = 10       # frames of aspect-ratio history kept per track
FALL_RATIO_DROP_THRESHOLD = 0.9   # how much the height/width ratio must fall to flag a fall
FALL_ALERT_COOLDOWN = 15          # seconds between repeated fall alerts for the same track

person_model = YOLO("yolov8n.pt")
face_model = YOLO("backend/detection/models/yolov8n-face.pt")

known_track_ids = {}
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

reference_embeddings = []

pending_samples = {}
pending_samples_lock = threading.Lock()

# track_id -> deque of recent height/width ratios, and last fall alert time
ratio_history = {}
last_fall_alert = {}

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def lookup_person(photo_folder):
    """Resolve a recognized photo folder to a student or staff record.
    Returns {"person_type", "person_id", "label"} or None if unknown."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, roll_number FROM students WHERE photo_folder = %s;", (photo_folder,))
        row = cur.fetchone()
        if row:
            person = {"person_type": "student", "person_id": row[0], "label": f"{row[1]} ({row[2]})"}
        else:
            cur.execute("SELECT id, name, role FROM staff WHERE photo_folder = %s;", (photo_folder,))
            row = cur.fetchone()
            person = {"person_type": "staff", "person_id": row[0], "label": f"{row[1]} ({row[2]})"} if row else None
        cur.close()
        conn.close()
        return person
    except Exception as e:
        print("DB lookup error:", e)
        return None

def build_reference_embeddings():
    global reference_embeddings
    reference_embeddings = []
    if not os.path.isdir(KNOWN_FACES_DB):
        return
    for identity_folder in os.listdir(KNOWN_FACES_DB):
        folder_path = os.path.join(KNOWN_FACES_DB, identity_folder)
        if not os.path.isdir(folder_path):
            continue
        for photo_file in os.listdir(folder_path):
            if not photo_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            photo_path = os.path.join(folder_path, photo_file)
            try:
                embedding_objs = DeepFace.represent(
                    img_path=photo_path,
                    model_name="Facenet512",
                    detector_backend="mtcnn",
                    align=True,
                    enforce_detection=True
                )
                for obj in embedding_objs:
                    vec = np.array(obj["embedding"])
                    reference_embeddings.append((identity_folder, vec))
            except Exception as e:
                print(f"Skipping {photo_path}: could not embed ({e})")
    print(f"Reference embeddings built: {len(reference_embeddings)} vectors across "
          f"{len(set(f for f, _ in reference_embeddings))} identities.")

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def get_tight_face_crop(person_crop):
    if person_crop.size == 0:
        return None
    try:
        face_results = face_model(person_crop, verbose=False)
        boxes = face_results[0].boxes.xyxy.cpu().numpy()
        confs = face_results[0].boxes.conf.cpu().numpy()
        if len(boxes) == 0:
            return None
        best_idx = confs.argmax()
        if confs[best_idx] < FACE_DETECTION_MIN_CONFIDENCE:
            return None
        fx1, fy1, fx2, fy2 = map(int, boxes[best_idx])
        face_crop = person_crop[max(0,fy1):fy2, max(0,fx1):fx2]
        if face_crop.size == 0 or face_crop.shape[0] < 40 or face_crop.shape[1] < 40:
            return None
        return face_crop
    except Exception:
        return None

def match_single_frame(face_crop):
    if not reference_embeddings:
        return None, 0
    try:
        embedding_objs = DeepFace.represent(
            img_path=face_crop,
            model_name="Facenet512",
            detector_backend="skip",
            align=True,
            enforce_detection=False
        )
        if not embedding_objs:
            return None, 0
        live_vec = np.array(embedding_objs[0]["embedding"])

        best_identity = None
        best_score = -1
        for identity_folder, ref_vec in reference_embeddings:
            score = cosine_similarity(live_vec, ref_vec)
            if score > best_score:
                best_score = score
                best_identity = identity_folder

        if best_score >= MATCH_SIMILARITY_THRESHOLD:
            return best_identity, best_score
        return None, best_score
    except Exception:
        return None, 0

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

def add_event(event_type, track_id, label, person=None, confidence=None):
    """person: {"person_type", "person_id"} of the recognized student/staff
    member, or None (unknown person, crowd alert). Views filter on these IDs,
    never on the label text. The event goes to the live WebSocket and the
    in-memory log right away, and to PostgreSQL via a background queue."""
    event = {
        "type": event_type,
        "track_id": int(track_id) if track_id is not None else None,
        "label": label,
        "person_type": person["person_type"] if person else None,
        "person_id": person["person_id"] if person else None,
        "camera": event_store.CAMERA_NAME,
        "confidence": round(float(confidence), 3) if confidence is not None else None,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with events_lock:
        events_log.append(event)
        if len(events_log) > 100:
            events_log.pop(0)
    event_store.enqueue(event)      # non-blocking; written to the database in the background
    broadcast_event(event)

def check_crowd(person_count):
    global last_crowd_alert_time
    now = time.time()
    if person_count >= CROWD_THRESHOLD and (now - last_crowd_alert_time) > CROWD_ALERT_COOLDOWN:
        last_crowd_alert_time = now
        add_event("CROWD_ALERT", None, f"{person_count} people detected in frame")
        print(f"[CROWD ALERT] {person_count} people detected at {time.strftime('%H:%M:%S')}")

def check_fall(track_id, box_width, box_height, label, person=None):
    """Heuristic: a standing person's box is tall (h/w > 1.3ish); a fallen person's box
    is wide/short (h/w drops sharply). We watch for a fast transition, not just a static wide box,
    to avoid false positives on people who are simply sitting or crouching slowly."""
    if box_width <= 0:
        return
    ratio = box_height / box_width

    if track_id not in ratio_history:
        ratio_history[track_id] = deque(maxlen=FALL_RATIO_HISTORY_LEN)
    ratio_history[track_id].append(ratio)

    history = ratio_history[track_id]
    if len(history) < FALL_RATIO_HISTORY_LEN:
        return  # not enough history yet

    max_ratio = max(list(history)[:5])   # tallest (most "standing") in the earlier half
    min_ratio = min(list(history)[5:])   # shortest (most "fallen") in the recent half

    drop = max_ratio - min_ratio

    if drop > FALL_RATIO_DROP_THRESHOLD and min_ratio < 0.9:
        now = time.time()
        last_alert = last_fall_alert.get(track_id, 0)
        if (now - last_alert) > FALL_ALERT_COOLDOWN:
            last_fall_alert[track_id] = now
            add_event("FALL_DETECTED", track_id, label + " — possible fall detected", person)
            print(f"[FALL ALERT] Track ID {track_id}: {label} at {time.strftime('%H:%M:%S')} (ratio drop={drop:.2f})")

def run_voting_recognition(track_id):
    try:
        votes = []
        scores = []
        for _ in range(VOTE_SAMPLE_COUNT):
            with pending_samples_lock:
                crop = pending_samples.get(track_id)
            if crop is not None:
                face_crop = get_tight_face_crop(crop)
                if face_crop is not None:
                    identity, score = match_single_frame(face_crop)
                    votes.append(identity)
                    scores.append(score)
            time.sleep(VOTE_SAMPLE_INTERVAL)

        vote_counts = Counter(votes)
        person = None
        confidence = None
        if vote_counts:
            winner, count = vote_counts.most_common(1)[0]
            if winner is not None and count >= 2:
                person = lookup_person(winner)
                label = person["label"] if person else winner
                confidence = max(s for v, s in zip(votes, scores) if v == winner)
            else:
                label = "Unknown"
        else:
            label = "Unknown"

        if track_id in known_track_ids:
            known_track_ids[track_id]["label"] = label
            known_track_ids[track_id]["person"] = person
            known_track_ids[track_id]["status"] = "done"
            add_event("ENTRY", track_id, label, person, confidence)
            print(f"[ENTRY] Track ID {track_id}: {label} (votes={votes}, scores={[round(s,3) for s in scores]})")
    finally:
        with recognition_results_lock:
            recognition_in_progress.discard(track_id)
        with pending_samples_lock:
            pending_samples.pop(track_id, None)

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
    source = int(CAMERA_SOURCE) if CAMERA_SOURCE.isdigit() else CAMERA_SOURCE
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Error: Could not open camera source {CAMERA_SOURCE!r}.")
        return

    print("Background tracking loop started.")

    frame_counter = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_counter += 1

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
                person_crop = frame[max(0,y1):y2, max(0,x1):x2].copy()

                if track_id not in known_track_ids:
                    known_track_ids[track_id] = {
                        "label": "Identifying...",
                        "entry_time": time.time(),
                        "last_seen": time.time(),
                        "status": "pending"
                    }
                    with pending_samples_lock:
                        pending_samples[track_id] = person_crop
                    with recognition_results_lock:
                        if track_id not in recognition_in_progress:
                            recognition_in_progress.add(track_id)
                            recognition_executor.submit(run_voting_recognition, track_id)
                else:
                    known_track_ids[track_id]["last_seen"] = time.time()
                    with pending_samples_lock:
                        if track_id in pending_samples:
                            pending_samples[track_id] = person_crop

                label_text = known_track_ids[track_id]["label"]

                # Fall detection runs every frame using the cheap bounding-box heuristic
                box_w = x2 - x1
                box_h = y2 - y1
                check_fall(track_id, box_w, box_h, label_text, known_track_ids[track_id].get("person"))

                if label_text == "Identifying...":
                    box_color = (0, 165, 255)
                elif label_text == "Unknown":
                    box_color = (0, 0, 220)
                else:
                    box_color = (0, 200, 0)
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
                add_event("EXIT", track_id, label, known_track_ids[track_id].get("person"))
                print(f"[EXIT] Track ID {track_id}: {label}")
            del known_track_ids[track_id]
            ratio_history.pop(track_id, None)
            last_fall_alert.pop(track_id, None)

        update_latest_frame(frame)

    cap.release()

def start_background_tracking():
    event_store.start()
    build_reference_embeddings()
    thread = threading.Thread(target=run_tracking_loop, daemon=True)
    thread.start()
