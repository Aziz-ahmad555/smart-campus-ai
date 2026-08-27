import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from backend.tracking import engine

app = FastAPI(title="Smart Campus AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    engine.main_event_loop = asyncio.get_event_loop()
    engine.start_background_tracking()

@app.get("/")
def read_root():
    return {"message": "Smart Campus AI backend is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/events")
def get_events():
    with engine.events_lock:
        return {"events": list(engine.events_log)}

@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    engine.connected_websockets.append(websocket)
    print(f"WebSocket client connected. Total clients: {len(engine.connected_websockets)}")
    try:
        while True:
            await websocket.receive_text()  # keep connection alive, ignore incoming messages
    except WebSocketDisconnect:
        engine.connected_websockets.remove(websocket)
        print(f"WebSocket client disconnected. Total clients: {len(engine.connected_websockets)}")
