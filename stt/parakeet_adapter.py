"""Pipecat adapter that feeds audio into Parakeet and emits transcripts."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from pipecat.frames.frames import Frame, InputAudioRawFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.utils.time import time_now_iso8601

from stt.parakeet_service import ParakeetService


class EndOfUtteranceFrame(Frame):
    """Signal that the ASR detected the end of an utterance."""

    pass


class ParakeetSTTAdapter(FrameProcessor):
    def __init__(
        self,
        service: ParakeetService,
        *,
        prepend_prompt: str = "",
        append_prompt: str = "",
    ) -> None:
        super().__init__()
        self._service = service
        self._prepend_prompt = prepend_prompt
        self._append_prompt = append_prompt
        self._audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        self._transcribe_task: Optional[asyncio.Task[None]] = None

    async def _audio_generator(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                break
            yield chunk

    async def _drain_transcripts(self):
        async for segment in self._service.stream_transcription(self._audio_generator()):
            if not segment.text:
                continue
            text = f"{self._prepend_prompt}{segment.text}{self._append_prompt}".strip()
            transcript = TranscriptionFrame(
                text=text,
                user_id="anonymous",
                timestamp=time_now_iso8601(),
                result=segment,
            )
            await self.push_frame(transcript, FrameDirection.DOWNSTREAM)
            if segment.end_of_utterance:
                await self.push_frame(EndOfUtteranceFrame(), FrameDirection.DOWNSTREAM)

    async def _ensure_transcriber(self):
        if not self._transcribe_task or self._transcribe_task.done():
            self._transcribe_task = asyncio.create_task(self._drain_transcripts())

    async def _stop_transcriber(self):
        if self._transcribe_task and not self._transcribe_task.done():
            await self._audio_queue.put(None)
            await self._transcribe_task
            self._transcribe_task = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, InputAudioRawFrame):
            await self._ensure_transcriber()
            await self._audio_queue.put(frame.audio)
        else:
            # Pass through non-audio frames untouched.
            await self.push_frame(frame, direction)

        # If the upstream signals a stop (common for EndFrame), close the stream.
        if frame.__class__.__name__ == "EndFrame":
            await self._stop_transcriber()
