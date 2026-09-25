"""Enrol a person's face from the webcam, as extra reference photos.

    python evaluation/enroll_webcam.py --person AzizAhmad --count 15

Phone photos and live webcam frames look different (lens, lighting,
resolution, compression), and the live pipeline compares webcam faces with
the reference photos. Adding webcam photos of the same person closes that gap.

The frames are checked with the same rules the live pipeline uses: the
YOLOv8n-face detector, confidence >= FACE_DETECTION_MIN_CONFIDENCE (0.55) and
a face of at least 40 x 40 px. Exactly one face must be in view, so nobody
else gets enrolled by accident, and MTCNN (which builds the reference
embeddings) must also find exactly one face. Only frames that pass are saved,
to data/known_faces/<person>/ (git-ignored), as the face with some margin.
The script asks you to turn your head a little (straight, left, right, up,
down) so the references cover the poses seen on camera.

Nothing is changed in the database. <person> must be the photo folder of a
student or staff member for recognition to name them. Restart the API
afterwards so it rebuilds the reference embeddings.
"""
import argparse
import os
import sys
import time

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)                    # the engine loads its models by relative path
sys.path.insert(0, ROOT)

from backend.tracking import engine  # noqa: E402  (same models and thresholds as live)

POSES = [
    "look straight at the camera",
    "turn your head slightly to the LEFT",
    "turn your head slightly to the RIGHT",
    "tilt your head slightly UP",
    "tilt your head slightly DOWN",
]
MIN_FACE_PX = 40                  # as in engine.get_tight_face_crop
MARGIN = 0.4                      # saved around the face, so MTCNN can find and align it
SECONDS_BETWEEN_SAVES = 0.6       # spreads the photos out within a pose
SECONDS_PER_POSE_PROMPT = 3


def check_frame(frame):
    """(face box, reason). The box is None when the frame isn't good enough."""
    result = engine.face_model(frame, verbose=False)[0]
    boxes = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    faces = [(b, c) for b, c in zip(boxes, confs) if c >= engine.FACE_DETECTION_MIN_CONFIDENCE]
    if not faces:
        best = f" (best confidence {confs.max():.2f})" if len(confs) else ""
        return None, "no clear face" + best
    if len(faces) > 1:
        return None, "more than one face in view"
    (x1, y1, x2, y2), conf = faces[0]
    if x2 - x1 < MIN_FACE_PX or y2 - y1 < MIN_FACE_PX:
        return None, f"face too small ({int(x2 - x1)}x{int(y2 - y1)} px) - move closer"
    return (int(x1), int(y1), int(x2), int(y2)), f"ok (confidence {conf:.2f})"


def with_margin(frame, box):
    x1, y1, x2, y2 = box
    mx, my = int((x2 - x1) * MARGIN), int((y2 - y1) * MARGIN)
    h, w = frame.shape[:2]
    return frame[max(0, y1 - my):min(h, y2 + my), max(0, x1 - mx):min(w, x2 + mx)].copy()


def mtcnn_finds_one_face(image):
    try:
        faces = engine.DeepFace.extract_faces(img_path=image, detector_backend="mtcnn",
                                              enforce_detection=True, align=True)
    except Exception:
        return False
    return len(faces) == 1


def show(frame, lines, preview):
    if not preview:
        return True
    view = frame.copy()
    for i, text in enumerate(lines):
        cv2.putText(view, text, (10, 25 + 25 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
        cv2.putText(view, text, (10, 25 + 25 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.imshow("Webcam enrolment (q to stop)", view)
    return cv2.waitKey(1) & 0xFF != ord("q")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--person", required=True, help="photo folder name, e.g. AzizAhmad")
    parser.add_argument("--count", type=int, default=15, help="photos to save (default 15)")
    parser.add_argument("--camera", default=engine.CAMERA_SOURCE, help="camera index or URL (default: CAMERA_SOURCE)")
    parser.add_argument("--no-preview", action="store_true", help="don't open a preview window")
    args = parser.parse_args()

    if not args.person.replace("_", "").replace("-", "").isalnum():
        sys.exit("--person must be a folder name: letters, digits, - and _ only")
    folder = os.path.join(engine.KNOWN_FACES_DB, args.person)
    if not os.path.isdir(folder):
        print(f"Note: {folder} doesn't exist yet and will be created. Recognition only names this person "
              f"if a student or staff member has '{args.person}' as their photo folder.")

    source = int(args.camera) if str(args.camera).isdigit() else args.camera
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        sys.exit("Camera not available. Is the API (or another program) using it? Stop it and try again.")
    preview = not args.no_preview

    per_pose = [args.count // len(POSES) + (i < args.count % len(POSES)) for i in range(len(POSES))]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    saved, rejected = [], {}
    try:
        for pose, wanted in zip(POSES, per_pose):
            if wanted == 0:
                continue
            print(f"\n>>> Now {pose}.", flush=True)
            prompt_until = time.time() + SECONDS_PER_POSE_PROMPT
            got, last_save = 0, 0.0
            while got < wanted:
                ok, frame = cap.read()
                if not ok:
                    continue
                if time.time() < prompt_until:              # give time to move into the pose
                    left = int(prompt_until - time.time()) + 1
                    if not show(frame, [f"Next: {pose}", f"starting in {left}s"], preview):
                        raise KeyboardInterrupt
                    continue
                box, reason = check_frame(frame)
                status = f"{pose}: {got}/{wanted} saved"
                if not show(frame, [status, reason], preview):
                    raise KeyboardInterrupt
                if box is None:
                    rejected[reason.split(" (")[0]] = rejected.get(reason.split(" (")[0], 0) + 1
                    continue
                if time.time() - last_save < SECONDS_BETWEEN_SAVES:
                    continue
                photo = with_margin(frame, box)
                if not mtcnn_finds_one_face(photo):
                    rejected["MTCNN could not align the face"] = rejected.get("MTCNN could not align the face", 0) + 1
                    continue
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, f"webcam_{stamp}_{len(saved) + 1:02d}.jpg")
                cv2.imwrite(path, photo, [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved.append(path)
                got += 1
                last_save = time.time()
                print(f"  saved {len(saved)}/{args.count}  {reason}", flush=True)
    except KeyboardInterrupt:
        print("\nStopped early.")
    finally:
        cap.release()
        if preview:
            cv2.destroyAllWindows()

    print(f"\nSaved {len(saved)} photo(s) to {os.path.abspath(folder)}")
    if rejected:
        print("Frames skipped: " + ", ".join(f"{k}: {v}" for k, v in sorted(rejected.items())))
    if saved:
        print("Restart the API so it rebuilds the reference embeddings. To check that strangers are still "
              "rejected, run: python evaluation/evaluate_recognition.py and "
              "python -m pytest tests/test_recheck.py -k stranger")


if __name__ == "__main__":
    main()
