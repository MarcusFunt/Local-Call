"""Adapter that streams text tokens to VibeVoice and emits audio frames."""
from __future__ import annotations

import asyncio
import contextlib
from typing import AsyncIterator, List, Optional

from pipecat.frames.frames import Frame, TextFrame, AudioFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from tts.vibevoice_service import VibeVoiceService


class VibeVoiceAdapter(FrameProcessor):
    """Convert streamed :class:`TextFrame` tokens into VibeVoice audio."""

    def __init__(
        self,
        service: VibeVoiceService,
        *,
        streaming_mode: bool = True,
        flush_on_punctuation: bool = True,
        flush_char_threshold: int = 120,
    ) -> None:
        super().__init__()
        self._service = service
        self._streaming_mode = streaming_mode
        self._flush_on_punctuation = flush_on_punctuation
        self._flush_char_threshold = flush_char_threshold
        self._buffer: List[str] = []
        self._text_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._stream_task: Optional[asyncio.Task[None]] = None
        self._burst_task: Optional[asyncio.Task[None]] = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, TextFrame):
            self._buffer.append(frame.text)
            if self._streaming_mode:
                await self._ensure_streaming()
                await self._flush_buffer(streaming=True)
            elif self._should_flush(frame.text):
                await self._flush_buffer(streaming=False)
            return

        if frame.__class__.__name__ == "StartInterruptionFrame":
            await self._cancel_playback()
            return

        if frame.__class__.__name__ == "EndFrame":
            await self._flush_buffer(streaming=self._streaming_mode, force=True)
            if self._streaming_mode:
                await self._stop_streaming()
            else:
                await self._drain_burst_task()
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    async def _text_generator(self) -> AsyncIterator[str]:
        while True:
            text = await self._text_queue.get()
            if text is None:
                break
            yield text

    async def _stream_audio(self):
        async for audio in self._service.stream_synthesis(self._text_generator()):
            await self.push_frame(AudioFrame(audio), FrameDirection.DOWNSTREAM)

    async def _ensure_streaming(self):
        if not self._stream_task or self._stream_task.done():
            self._stream_task = asyncio.create_task(self._stream_audio())

    async def _stop_streaming(self):
        if self._stream_task and not self._stream_task.done():
            await self._text_queue.put(None)
            try:
                await self._stream_task
            finally:
                self._stream_task = None

    async def _drain_burst_task(self):
        if self._burst_task:
            try:
                await self._burst_task
            finally:
                self._burst_task = None

    async def _flush_buffer(self, *, streaming: bool, force: bool = False):
        if not self._buffer:
            return

        text = "".join(self._buffer).strip()
        if not text:
            self._buffer.clear()
            return

        if not force and not streaming and not self._should_flush(text):
            return

        self._buffer.clear()
        if streaming:
            await self._text_queue.put(text)
        else:
            await self._drain_burst_task()
            self._burst_task = asyncio.create_task(self._play_burst(text))

    def _should_flush(self, latest_text: str) -> bool:
        if not self._buffer and not latest_text:
            return False
        combined = "".join(self._buffer) or latest_text
        if self._flush_on_punctuation and any(p in combined for p in {".", "!", "?"}):
            return True
        if self._flush_char_threshold and len(combined) >= self._flush_char_threshold:
            return True
        return False

    async def _play_burst(self, text: str):
        async for audio in self._service.synthesize_burst(text):
            await self.push_frame(AudioFrame(audio), FrameDirection.DOWNSTREAM)

    async def _cancel_playback(self):
        self._buffer.clear()
        if self._streaming_mode:
            await self._service.cancel()
            if self._stream_task:
                self._stream_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._stream_task
                self._stream_task = None
            while not self._text_queue.empty():
                try:
                    self._text_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
        else:
            if self._burst_task:
                self._burst_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._burst_task
                self._burst_task = None
            await self._service.cancel()
