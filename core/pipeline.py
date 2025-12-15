"""Voice agent pipeline wiring for Local-Call."""
from __future__ import annotations

from pathlib import Path

from pipecat.frames.frames import (
    BotInterruptionFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    InputAudioRawFrame,
    InterruptionFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.transcript_processor import TranscriptProcessor

from core.configuration import ProfileConfig
from llm.model_router import ModelRouter
from llm.ollama_client import OllamaClient
from stt.whisper_cpp_adapter import WhisperCPPAdapter
from stt.whisper_cpp_service import WhisperCPPService
from tools.registry import create_default_registry
from tts.xtts_streaming_adapter import XTTSStreamingAdapter
from tts.xtts_streaming_service import XTTSStreamingService


class BargeInController(FrameProcessor):
    """Emit interruption frames when the user speaks over the assistant."""

    def __init__(self) -> None:
        super().__init__()
        self._assistant_speaking = False

    async def process_frame(self, frame, direction: FrameDirection):
        if isinstance(frame, BotStartedSpeakingFrame):
            self._assistant_speaking = True
        elif isinstance(frame, (BotStoppedSpeakingFrame, BotInterruptionFrame, InterruptionFrame)):
            self._assistant_speaking = False

        if isinstance(frame, CancelFrame):
            self._assistant_speaking = False

        if isinstance(frame, InputAudioRawFrame) and self._assistant_speaking:
            # Interrupt downstream processors before letting the new audio through.
            await self.push_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
            self._assistant_speaking = False

        await self.push_frame(frame, direction)


class ContextFrames:
    """Factory wrapper for transcript processors used in the pipeline."""

    def __init__(self) -> None:
        self._transcript = TranscriptProcessor()

    def user(self):
        return self._transcript.user()

    def assistant(self):
        return self._transcript.assistant()


def create_pipeline(profile: ProfileConfig, transport) -> Pipeline:
    """Create a configured pipeline for the given profile and transport."""

    dev_mode = profile.name != "prod"

    whisper_service = WhisperCPPService(
        server_url=profile.stt.server_url,
    )

    stt_adapter = WhisperCPPAdapter(
        whisper_service,
        buffer_size_ms=profile.stt.buffer_size_ms,
        silence_timeout_ms=profile.stt.silence_timeout_ms,
    )

    model_router = ModelRouter(
        persona_path=Path(profile.llm.persona_path),
        min_vram_gb=profile.llm.min_vram_gb,
        override_model=profile.llm.model_override,
    )
    system_prompt = model_router.load_persona()
    tool_registry = create_default_registry()

    llm_client = OllamaClient(
        model_router=model_router,
        tool_registry=tool_registry,
        profile=profile.name,
        system_prompt=system_prompt,
        host=profile.llm.host,
        tool_call_limit=profile.llm.tool_call_limit,
    )

    xtts_service = XTTSStreamingService(
        server_url=profile.tts.server_url,
    )
    tts_adapter = XTTSStreamingAdapter(
        xtts_service,
    )

    barge_in = BargeInController()
    context = ContextFrames()

    return Pipeline(
        [
            transport.input(),
            barge_in,
            stt_adapter,
            context.user(),
            llm_client,
            tts_adapter,
            transport.output(),
            context.assistant(),
        ]
    )


def create_stub_pipeline(profile: ProfileConfig, transport):
    """Alias maintained for backwards compatibility."""

    return create_pipeline(profile, transport)
