import os
import cv2
import time
import threading
import asyncio
import numpy as np
from collections import Counter
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
FACE_DETECTION_MIN_CONFIDENCE = 0.55
MATCH_SIMILARITY_THRESHOLD = 0.62
VOTE_SAMPLE_COUNT = 3       # how many frames to sample before deciding
VOTE_SAMPLE_INTERVAL = 0.35 # seconds between samples

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

# Buffers of pending crops per track_id, collected across multiple frames before voting
pending_samples = {}
pending_samples_lock = threading.Lock()

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
    """Returns (identity_or_None, score) for ONE frame's face crop."""
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

def run_voting_recognition(track_id):
    """Collects VOTE_SAMPLE_COUNT face crops over time, then decides by majority vote."""
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
                    votes.append(identity)  # None counts as "Unknown" vote
                    scores.append(score)
            time.sleep(VOTE_SAMPLE_INTERVAL)

        # Majority vote among the collected samples
        vote_counts = Counter(votes)
        if vote_counts:
            winner, count = vote_counts.most_common(1)[0]
            if winner is not None and count >= 2:  # at least 2 of 3 must agree
                photo_folder = winner
                student_info = lookup_student(photo_folder)
                label = student_info if student_info else photo_folder
            else:
                label = "Unknown"
        else:
            label = "Unknown"

        if track_id in known_track_ids:
            known_track_ids[track_id]["label"] = label
            known_track_ids[track_id]["status"] = "done"
            add_event("ENTRY", track_id, label)
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
                    # Keep updating the pending sample with the freshest crop while voting is in progress
                    with pending_samples_lock:
                        if track_id in pending_samples:
                            pending_samples[track_id] = person_crop

                label_text = known_track_ids[track_id]["label"]
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
                add_event("EXIT", track_id, label)
                print(f"[EXIT] Track ID {track_id}: {label}")
            del known_track_ids[track_id]

        update_latest_frame(frame)

    cap.release()

def start_background_tracking():
    build_reference_embeddings()
    thread = threading.Thread(target=run_tracking_loop, daemon=True)
    thread.start()
