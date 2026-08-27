from fastapi import FastAPI
from backend.tracking.engine import start_background_tracking, events_log, events_lock

app = FastAPI(title="Smart Campus AI API")

@app.on_event("startup")
def startup_event():
    start_background_tracking()

@app.get("/")
def read_root():
    return {"message": "Smart Campus AI backend is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/events")
def get_events():
    with events_lock:
        return {"events": list(events_log)}
