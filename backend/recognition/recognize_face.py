from deepface import DeepFace
import cv2
import os

# Path to your known-faces database (one subfolder per person)
KNOWN_FACES_DB = "data/known_faces"

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
            # os.path handles Windows and Unix-style paths correctly
            person_name = os.path.basename(os.path.dirname(best_match_path))
            label = person_name
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