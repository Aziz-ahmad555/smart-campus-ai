import time
import cv2
from ultralytics import YOLO

person_model = YOLO("yolov8n.pt")
face_model = YOLO("backend/detection/models/yolov8n-face.pt")

NUM_FRAMES = 60  # how many frames to benchmark per test

def benchmark_person_detection(cap):
    print("\n--- Benchmarking Person Detection (YOLOv8n) ---")
    times = []
    for _ in range(NUM_FRAMES):
        ret, frame = cap.read()
        if not ret:
            break
        start = time.time()
        person_model(frame, classes=[0], verbose=False)
        times.append(time.time() - start)
    avg_time = sum(times) / len(times)
    fps = 1 / avg_time
    print(f"Avg inference time: {avg_time*1000:.1f} ms | FPS: {fps:.2f}")
    return fps

def benchmark_face_detection(cap):
    print("\n--- Benchmarking Face Detection (YOLOv8n-face) ---")
    times = []
    for _ in range(NUM_FRAMES):
        ret, frame = cap.read()
        if not ret:
            break
        start = time.time()
        face_model(frame, verbose=False)
        times.append(time.time() - start)
    avg_time = sum(times) / len(times)
    fps = 1 / avg_time
    print(f"Avg inference time: {avg_time*1000:.1f} ms | FPS: {fps:.2f}")
    return fps

def benchmark_tracking(cap):
    print("\n--- Benchmarking Person Tracking (YOLOv8n + ByteTrack) ---")
    times = []
    for _ in range(NUM_FRAMES):
        ret, frame = cap.read()
        if not ret:
            break
        start = time.time()
        person_model.track(frame, classes=[0], persist=True, verbose=False)
        times.append(time.time() - start)
    avg_time = sum(times) / len(times)
    fps = 1 / avg_time
    print(f"Avg inference time: {avg_time*1000:.1f} ms | FPS: {fps:.2f}")
    return fps

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print(f"Running FPS benchmark ({NUM_FRAMES} frames per test)...")
    print("Stand in front of the camera for realistic results.")
    time.sleep(2)

    person_fps = benchmark_person_detection(cap)
    face_fps = benchmark_face_detection(cap)
    tracking_fps = benchmark_tracking(cap)

    cap.release()

    print("\n=== FPS BENCHMARK SUMMARY (CPU) ===")
    print(f"Person Detection:  {person_fps:.2f} FPS")
    print(f"Face Detection:    {face_fps:.2f} FPS")
    print(f"Tracking:          {tracking_fps:.2f} FPS")

    # Save results to CSV for later graphing
    import csv
    with open("evaluation/fps_results.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["stage", "fps"])
        writer.writerow(["Person Detection", round(person_fps, 2)])
        writer.writerow(["Face Detection", round(face_fps, 2)])
        writer.writerow(["Tracking", round(tracking_fps, 2)])
    print("\nResults saved to evaluation/fps_results.csv")

if __name__ == "__main__":
    main()
