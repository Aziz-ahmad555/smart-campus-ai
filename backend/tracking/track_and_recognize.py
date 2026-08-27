import os
import cv2
import time
import psycopg2
from dotenv import load_dotenv
from deepface import DeepFace
from ultralytics import YOLO

load_dotenv()

KNOWN_FACES_DB = "data/known_faces"
person_model = YOLO("yolov8n.pt")

# {track_id: {"label": ..., "entry_time": ..., "last_seen": ...}}
known_track_ids = {}

EXIT_TIMEOUT_SECONDS = 5  # if not seen for this long, consider them "exited"

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

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

print("Webcam started. Press 'q' to quit.")

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
                print(f"[ENTRY] Track ID {track_id}: {label} at {time.strftime('%H:%M:%S')}")
            else:
                known_track_ids[track_id]["last_seen"] = time.time()

            label = known_track_ids[track_id]["label"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID {track_id}: {label}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # Check for exits: anyone not seen recently and missing from this frame
    now = time.time()
    exited_ids = []
    for track_id, info in known_track_ids.items():
        if track_id not in current_frame_ids and (now - info["last_seen"]) > EXIT_TIMEOUT_SECONDS:
            exited_ids.append(track_id)

    for track_id in exited_ids:
        label = known_track_ids[track_id]["label"]
        print(f"[EXIT] Track ID {track_id}: {label} at {time.strftime('%H:%M:%S')}")
        del known_track_ids[track_id]

    cv2.imshow("Smart Campus AI - Entry/Exit Tracking", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
