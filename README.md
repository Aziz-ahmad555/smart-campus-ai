# Smart Campus AI — Real-Time Intelligent Surveillance & Access System

An end-to-end AI perception pipeline that detects people, recognizes faces, tracks identities across frames, and logs entry/exit events in real time — built from scratch with YOLOv8, DeepFace, PostgreSQL, FastAPI, and React.

This is not just a face recognition demo. It is a full system architecture: **camera ? detection ? recognition ? database ? tracking ? API ? live dashboard**, backed by structured evaluation of accuracy, latency, and robustness under real-world conditions.

## Architecture

\\\
RTSP/Webcam Feed
      |
YOLOv8 Person Detection
      |
YOLOv8-Face Face Detection
      |
DeepFace Recognition (embedding match)
      |
PostgreSQL Student Lookup
      |
ByteTrack Entry/Exit Tracking
      |
FastAPI Backend (REST API)
      |
React Real-Time Dashboard
\\\

## Features

- **Person detection** — YOLOv8n, real-time on CPU
- **Face detection** — YOLOv8n-face, purpose-trained model
- **Face recognition** — DeepFace embeddings matched against a known-faces database
- **Student identification** — recognized faces resolved to real student records via PostgreSQL
- **Entry/exit tracking** — persistent IDs across frames using ByteTrack, with timestamped entry/exit event logging
- **REST API** — FastAPI backend exposing live recognition/tracking events as JSON
- **Real-time dashboard** — React frontend polling the API and displaying live entry/exit events
- **Evaluation suite** — accuracy, FAR/FRR, and FPS benchmarking with automated chart generation

## Tech Stack

| Layer | Technology |
|---|---|
| Detection | YOLOv8 (Ultralytics) |
| Face Recognition | DeepFace (OpenCV backend) |
| Tracking | ByteTrack |
| Database | PostgreSQL |
| Backend | FastAPI, Uvicorn |
| Frontend | React (Vite) |
| Language | Python 3.11, JavaScript |
| Environment | CPU-only (no dedicated GPU) |

## Evaluation Results

### Recognition Accuracy Under Varying Conditions

Tested across 5 categories (3 images each) using held-out photos not present in the training/reference set.

![Accuracy by Condition](evaluation/accuracy_by_condition.png)

| Condition | Accuracy |
|---|---|
| Low light | 100.0% |
| Unknown person (rejection) | 100.0% |
| Normal / frontal | 66.7% |
| Different angle | 33.3% |
| Occluded | 33.3% |

**False Acceptance Rate (FAR): 0.0%** — the system never misidentified a stranger as a known student.
**False Rejection Rate (FRR): 41.7%** — the system sometimes failed to recognize the correct person under difficult conditions.

**Interpretation:** The system is heavily biased toward caution (zero false acceptances), which is the safer failure mode for an access-control context. Accuracy degrades under angle variation and occlusion, consistent with the known limitations of Haar Cascade-based face detection, which is optimized for frontal face geometry. A production system would likely benefit from a more robust detector such as RetinaFace or MTCNN.

### Pipeline Performance (FPS, CPU-only)

![FPS by Stage](evaluation/fps_by_stage.png)

| Stage | FPS | Avg Latency |
|---|---|---|
| Person Detection (YOLOv8n) | 6.79 | 147.3 ms |
| Face Detection (YOLOv8n-face) | 9.35 | 106.9 ms |
| Tracking (YOLOv8n + ByteTrack) | 7.35 | 136.1 ms |

All benchmarks were run on integrated (non-dedicated) CPU graphics. Real-time performance (30+ FPS) would require GPU acceleration; current throughput is sufficient for near-real-time entry logging but not high-frame-rate video analytics.

## Project Structure

\\\
smart-campus-ai/
+-- backend/
¦   +-- detection/       # YOLO person and face detection
¦   +-- recognition/     # DeepFace recognition logic
¦   +-- tracking/        # ByteTrack + entry/exit engine
¦   +-- api/             # FastAPI application
¦   +-- database/        # PostgreSQL connection/testing
+-- frontend/             # React dashboard (Vite)
+-- data/
¦   +-- known_faces/     # Reference photos per identity
¦   +-- test_images/     # Evaluation test set (5 conditions)
+-- evaluation/           # Benchmark scripts, results, charts
+-- README.md
\\\

## Setup

### Prerequisites
- Python 3.11
- Node.js 18+
- PostgreSQL 18+

### Backend
\\\ash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
\\\

Create a \.env\ file in the project root:
\\\
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smart_campus_db
DB_USER=postgres
DB_PASSWORD=your_password
\\\

Run the API:
\\\ash
uvicorn backend.api.main:app --reload
\\\

### Frontend
\\\ash
cd frontend
npm install
npm run dev
\\\

Visit \http://localhost:5173\.

## Known Limitations

- Face detection uses Haar Cascade (via DeepFace's default OpenCV backend), which struggles with non-frontal angles and partial occlusion
- Tracker IDs are not persistent across full disappearances from frame — a person leaving and re-entering is assigned a new ID (no long-term re-identification yet)
- CPU-only inference limits throughput to under 10 FPS per stage
- Evaluation dataset is small (15 test images); results are indicative, not statistically comprehensive

## Future Work

- Upgrade face detector to RetinaFace or MTCNN for improved angle/occlusion robustness
- Add long-term re-identification to preserve identity across full frame absences
- GPU deployment for real-time throughput
- Expand evaluation dataset for statistically robust metrics
- Add crowd density detection and pose-based behavior analysis (per original project scope)

## Author

Aziz Ahmad — Final Year Project
