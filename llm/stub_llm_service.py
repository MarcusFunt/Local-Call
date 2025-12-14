
"""
This module defines a stub implementation of a Language Model service.
"""
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import TextFrame, Frame
from pipecat.processors.frame_processor import FrameDirection

class StubLLMService(FrameProcessor):
    """
    A stub implementation of a Language Model service.
    This service simply returns a hardcoded text frame for any text frame it receives.
    """

    def __init__(self, text="I am a stub LLM."):
        super().__init__()
        self._text = text

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """
        Processes a text frame and returns a hardcoded text frame.
        """
        if isinstance(frame, TextFrame):
            await self.push_frame(TextFrame(self._text), direction)
        else:
            await self.push_frame(frame, direction)
