
"""
This module defines a stub implementation of a Text-to-Speech service.
"""
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import TextFrame, Frame, AudioFrame
from pipecat.processors.frame_processor import FrameDirection

class StubTTSService(FrameProcessor):
    """
    A stub implementation of a Text-to-Speech service.
    This service simply prints the text it receives to the console and
    sends a silent audio frame to the client.
    """

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """
        Processes a text frame and prints it to the console.
        """
        if isinstance(frame, TextFrame):
            print(f"TTS: {frame.text}")
            await self.push_frame(AudioFrame(b""), direction)
        else:
            await self.push_frame(frame, direction)
