import os
import cv2
import psycopg2
from dotenv import load_dotenv
from deepface import DeepFace

load_dotenv()

KNOWN_FACES_DB = "data/known_faces"

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
        else:
            return photo_folder
    except Exception as e:
        print("DB lookup error:", e)
        return photo_folder

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

print("Webcam started. Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to grab frame.")
        break

    try:
        results = DeepFace.find(
            img_path=frame,
            db_path=KNOWN_FACES_DB,
            enforce_detection=False,
            silent=True,
            detector_backend="opencv"
        )

        if len(results) > 0 and len(results[0]) > 0:
            best_match_path = results[0].iloc[0]["identity"]
            photo_folder = os.path.basename(os.path.dirname(best_match_path))
            label = lookup_student(photo_folder)
        else:
            label = "Unknown"

    except Exception as e:
        print("ERROR:", e)
        label = "No face detected"

    cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("Smart Campus AI - Face Recognition", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
