
"""
This module defines the main application entry point for the voice agent.
It starts a FastAPI server and exposes a WebSocket endpoint for clients
to connect to.
"""
import asyncio
import os
from fastapi import FastAPI, WebSocket
from dotenv import load_dotenv

from pipecat.transports.websocket_transport import WebSocketTransport
from core.pipeline import create_stub_pipeline
from core.session import Session

load_dotenv()

app = FastAPI()

@app.websocket("/voice")
async def voice(websocket: WebSocket):
    """
    Handles a WebSocket connection from a client.
    """
    await websocket.accept()

    # Create a WebSocket transport for the session.
    transport = WebSocketTransport(websocket)

    # Create a new session for the client.
    session = Session(transport)

    # Start the session.
    task = asyncio.create_task(session.start())

    try:
        # Wait for the session to complete.
        await task
    except asyncio.CancelledError:
        pass
    finally:
        # Stop the session.
        await session.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
