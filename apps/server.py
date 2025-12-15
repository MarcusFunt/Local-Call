
"""FastAPI server entry point for the voice agent."""

import asyncio
import os

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

from core.configuration import load_app_config
from core.session import Session

load_dotenv()

CONFIG_PATH = os.getenv("APP_CONFIG", "config/dev.yaml")
APP_CONFIG = load_app_config(CONFIG_PATH)

app = FastAPI()


@app.websocket("/voice")
async def voice(websocket: WebSocket):
    """Handle an incoming websocket voice session."""

    await websocket.accept()
    profile_name = websocket.query_params.get("profile") if websocket.query_params else None
    profile = APP_CONFIG.profile(profile_name)

    serializer = ProtobufFrameSerializer()
    params = FastAPIWebsocketParams(
        add_wav_header=APP_CONFIG.transport.add_wav_header,
        serializer=serializer,
        session_timeout=APP_CONFIG.transport.session_timeout,
    )
    transport = FastAPIWebsocketTransport(websocket, params)

    session = Session(transport, profile)
    task = asyncio.create_task(session.start())

    try:
        await task
    finally:
        await session.stop()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
