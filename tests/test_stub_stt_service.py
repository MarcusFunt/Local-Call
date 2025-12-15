import asyncio
import sys
from pathlib import Path
from typing import List, Tuple

from pipecat.frames.frames import EndFrame, InputAudioRawFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

sys.path.append(str(Path(__file__).resolve().parents[1]))

from stt.parakeet_adapter import EndOfUtteranceFrame
from stt.stub_stt_service import StubSTTService


async def _run_stub(transcripts) -> List[Tuple[object, FrameDirection]]:
    service = StubSTTService(transcripts=transcripts)
    captured: List[Tuple[object, FrameDirection]] = []

    async def _push(frame, direction):
        if isinstance(frame, (TranscriptionFrame, EndOfUtteranceFrame)):
            captured.append((frame, direction))

    service.push_frame = _push  # type: ignore[assignment]

    await service.process_frame(
        InputAudioRawFrame(audio=b"\x00\x01", sample_rate=16000, num_channels=1),
        FrameDirection.DOWNSTREAM,
    )
    await service.process_frame(EndFrame(), FrameDirection.DOWNSTREAM)
    return captured


def test_stub_stt_emits_end_of_utterance_frame():
    frames = asyncio.run(_run_stub(["hello <EOU>"]))

    assert len(frames) == 2
    transcript, direction = frames[0]
    assert isinstance(transcript, TranscriptionFrame)
    assert transcript.text == "hello"
    assert direction == FrameDirection.DOWNSTREAM

    end_of_utterance, eou_direction = frames[1]
    assert isinstance(end_of_utterance, EndOfUtteranceFrame)
    assert eou_direction == FrameDirection.DOWNSTREAM
