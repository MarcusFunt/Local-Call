
import asyncio
import logging
from fastapi import FastAPI, WebSocket, Response
from fastapi.staticfiles import StaticFiles
from core.custom_transport import JSONWebsocketTransport
from core.pipeline import create_pipeline
from core.configuration import get_config

logging.basicConfig(level=logging.INFO)

app = FastAPI()
app.mount("/", StaticFiles(directory="web", html=True), name="web")

@app.websocket("/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    config = get_config()
    transport = JSONWebsocketTransport(websocket)
    pipeline = create_pipeline(config, transport)
    await pipeline.run()
