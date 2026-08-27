from fastapi import FastAPI

app = FastAPI(title="Smart Campus AI API")

@app.get("/")
def read_root():
    return {"message": "Smart Campus AI backend is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
