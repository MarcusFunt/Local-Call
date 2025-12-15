"""WebSocket client for streaming speech synthesis via VibeVoice."""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
from typing import AsyncIterator, Optional

import websockets
from websockets import WebSocketClientProtocol


class VibeVoiceService:
    """Stream text to a VibeVoice server and yield audio frames.

    The service maintains a WebSocket connection to the VibeVoice server and
    forwards text chunks as they arrive.  It is designed to work in both true
    streaming mode (production) and burst mode (development).  In burst mode
    the caller typically sends larger chunks that have been buffered until a
    punctuation boundary so that CPU-only setups can keep up with synthesis.
    """

    def __init__(
        self,
        server_uri: str = "ws://localhost:8020/ws",
        *,
        voice: Optional[str] = None,
        dev_mode: bool = False,
        connect_timeout: float = 5.0,
    ) -> None:
        self._server_uri = server_uri
        self._voice = voice
        self._dev_mode = dev_mode
        self._connect_timeout = connect_timeout
        self._current_websocket: Optional[WebSocketClientProtocol] = None
        self._lock = asyncio.Lock()

    async def _connect(self) -> WebSocketClientProtocol:
        websocket = await websockets.connect(self._server_uri, open_timeout=self._connect_timeout, max_size=None)
        config: dict[str, str] = {}
        if self._voice:
            config["voice"] = self._voice
        if self._dev_mode:
            config["mode"] = "burst"
        if config:
            await websocket.send(json.dumps({"type": "config", **config}))
        self._current_websocket = websocket
        return websocket

    @staticmethod
    def _decode_audio(message: str | bytes) -> Optional[bytes]:
        if isinstance(message, bytes):
            return message
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return None
        audio_base64 = payload.get("audio")
        if isinstance(audio_base64, str):
            try:
                return base64.b64decode(audio_base64)
            except (ValueError, binascii.Error, TypeError):
                return None
        return None

    async def stream_synthesis(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Send text chunks and yield synthesized audio."""

        async with self._lock:
            websocket = await self._connect()

        async def sender():
            try:
                async for text in text_stream:
                    if not text:
                        continue
                    await websocket.send(json.dumps({"type": "text", "text": text}))
                await websocket.send(json.dumps({"type": "eos"}))
            except asyncio.CancelledError:
                raise
            except Exception:
                await websocket.close()
                raise

        send_task = asyncio.create_task(sender())
        try:
            async for message in websocket:
                audio = self._decode_audio(message)
                if audio:
                    yield audio
                else:
                    try:
                        payload = json.loads(message)
                        if payload.get("type") == "done":
                            break
                    except (TypeError, json.JSONDecodeError):
                        continue
        finally:
            if not send_task.done():
                send_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass
            await websocket.close()
            if self._current_websocket is websocket:
                self._current_websocket = None

    async def synthesize_burst(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize a single text chunk (useful for dev/burst mode)."""

        async def iterator():
            yield text

        async for audio in self.stream_synthesis(iterator()):
            yield audio

    async def cancel(self):
        """Cancel any in-flight synthesis request."""

        if self._current_websocket:
            await self._current_websocket.close(code=1011, reason="cancelled")
            self._current_websocket = None
