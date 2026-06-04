from fastapi import FastAPI
from dispatcher.dispatcher import dispatch

app = FastAPI()


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/extract")
async def extract(payload: dict):
    result = dispatch(payload)
    return result
