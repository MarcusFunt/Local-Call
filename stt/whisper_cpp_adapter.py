
import asyncio
from pipecat.frames.frames import Frame, InputAudioRawFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.utils.time import time_now_iso8601
from typing import AsyncIterator
from .whisper_cpp_service import WhisperCPPService

class EndOfUtteranceFrame(Frame):
    """Signal that the ASR detected the end of an utterance."""
    pass

class WhisperCPPAdapter(FrameProcessor):
    def __init__(self, service: WhisperCPPService, buffer_size_ms: int = 2000, silence_timeout_ms: int = 500):
        super().__init__()
        self._service = service
        self._buffer_size_ms = buffer_size_ms
        self._silence_timeout_ms = silence_timeout_ms
        self._audio_buffer = bytearray()
        self._last_audio_time = None
        self._transcribe_task = None

    async def _transcribe(self):
        if not self._audio_buffer:
            return

        async def audio_generator():
            yield self._audio_buffer

        async for text in self._service.stream_transcription(audio_generator()):
            if text:
                transcript = TranscriptionFrame(
                    text=text,
                    user_id="anonymous",
                    timestamp=time_now_iso8601(),
                )
                await self.push_frame(transcript, FrameDirection.DOWNSTREAM)
                await self.push_frame(EndOfUtteranceFrame(), FrameDirection.DOWNSTREAM)

        self._audio_buffer.clear()

    async def _silence_detector(self):
        while True:
            if self._last_audio_time and (asyncio.get_event_loop().time() - self._last_audio_time) * 1000 > self._silence_timeout_ms:
                await self._transcribe()
            await asyncio.sleep(self._silence_timeout_ms / 1000)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, InputAudioRawFrame):
            if not self._transcribe_task:
                self._transcribe_task = asyncio.create_task(self._silence_detector())

            self._audio_buffer.extend(frame.audio)
            self._last_audio_time = asyncio.get_event_loop().time()

            # Assuming 16kHz, 16-bit mono audio
            buffer_duration_ms = len(self._audio_buffer) / (16000 * 2) * 1000
            if buffer_duration_ms >= self._buffer_size_ms:
                await self._transcribe()
        else:
            await self.push_frame(frame, direction)

        if frame.__class__.__name__ == "EndFrame":
            if self._transcribe_task:
                self._transcribe_task.cancel()
            await self._transcribe()
