from ultralytics import YOLO
import cv2

# Load the face-specific YOLO model
face_model = YOLO("backend/detection/models/yolov8n-face.pt")

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

    results = face_model(frame, verbose=False)
    annotated_frame = results[0].plot()

    cv2.imshow("Smart Campus AI - Face Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()