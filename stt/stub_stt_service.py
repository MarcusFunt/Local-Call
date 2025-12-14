
"""
This module defines a stub implementation of a Speech-to-Text service.
"""
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import AudioFrame, TextFrame, Frame
from pipecat.processors.frame_processor import FrameDirection

class StubSTTService(FrameProcessor):
    """
    A stub implementation of a Speech-to-Text service.
    This service simply returns a hardcoded text frame for any audio frame it receives.
    """

    def __init__(self, text="Hello, world!"):
        super().__init__()
        self._text = text

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """
        Processes a frame of audio and returns a hardcoded text frame.
        """
        if isinstance(frame, AudioFrame):
            await self.push_frame(TextFrame(self._text), direction)
        else:
            await self.push_frame(frame, direction)
