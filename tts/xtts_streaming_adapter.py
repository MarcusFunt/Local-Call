
import asyncio
from pipecat.frames.frames import Frame, TextFrame, AudioFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from typing import AsyncIterator
from .xtts_streaming_service import XTTSStreamingService

class XTTSStreamingAdapter(FrameProcessor):
    def __init__(self, service: XTTSStreamingService):
        super().__init__()
        self._service = service
        self._text_queue = asyncio.Queue()
        self._synthesis_task = None

    async def _text_generator(self) -> AsyncIterator[str]:
        while True:
            text = await self._text_queue.get()
            if text is None:
                break
            yield text

    async def _drain_audio(self):
        async for audio in self._service.stream_synthesis(self._text_generator()):
            if audio:
                await self.push_frame(AudioFrame(audio), FrameDirection.DOWNSTREAM)

    async def _ensure_synthesis(self):
        if not self._synthesis_task or self._synthesis_task.done():
            self._synthesis_task = asyncio.create_task(self._drain_audio())

    async def _stop_synthesis(self):
        if self._synthesis_task and not self._synthesis_task.done():
            await self._text_queue.put(None)
            await self._synthesis_task
            self._synthesis_task = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, TextFrame):
            await self._ensure_synthesis()
            await self._text_queue.put(frame.text)
        else:
            await self.push_frame(frame, direction)

        if frame.__class__.__name__ == "EndFrame":
            await self._stop_synthesis()
