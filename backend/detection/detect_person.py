from ultralytics import YOLO
import cv2

# Load a pretrained YOLO model (downloads automatically first run, ~6MB)
model = YOLO("yolov8n.pt")  # 'n' = nano, smallest/fastest version — good for CPU

# Open the default webcam (0 = first camera on your system)
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

    results = model(frame, classes=[0], verbose=False)
    annotated_frame = results[0].plot()

    cv2.imshow("Smart Campus AI - Person Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()