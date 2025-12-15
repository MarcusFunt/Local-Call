"""
Voice agent pipeline wiring using Parakeet for speech recognition.
"""
from pathlib import Path

from pipecat.pipeline.pipeline import Pipeline

from llm.model_router import ModelRouter
from llm.ollama_client import OllamaClient
from stt.parakeet_adapter import ParakeetSTTAdapter
from stt.parakeet_service import ParakeetService
from tools.registry import create_default_registry
from tts.vibevoice_adapter import VibeVoiceAdapter
from tts.vibevoice_service import VibeVoiceService


DEFAULT_RIVA_URI = "localhost:50051"


def create_pipeline(
    profile: str = "dev",
    *,
    riva_uri: str = DEFAULT_RIVA_URI,
    ollama_host: str = "http://localhost:11434",
    prepend_prompt: str = "",
    append_prompt: str = "",
    dev_buffer_ms: int = 2000,
    dev_max_buffer_ms: int = 8000,
    end_of_utterance_token: str = "<EOU>",
    sample_rate_hz: int = 16000,
    persona_path: str = "config/persona_default.md",
    min_vram_gb: int = 12,
    model_override: str | None = None,
    tool_call_limit: int = 3,
    vibevoice_uri: str = "ws://localhost:8020/ws",
    vibevoice_voice: str | None = None,
    flush_on_punctuation: bool = True,
    flush_char_threshold: int = 120,
):
    """Create a pipeline configured for production or development.

    Args:
        profile: Either ``"prod"`` (true streaming) or ``"dev"`` (buffered batches).
        riva_uri: URI of the running Riva server.
        ollama_host: Base URL for the Ollama API endpoint.
        prepend_prompt: Optional text prepended to each transcript.
        append_prompt: Optional text appended to each transcript (e.g., guidance).
        dev_buffer_ms: Buffer window used in development mode before decoding.
        dev_max_buffer_ms: Maximum buffer size in development mode.
        end_of_utterance_token: Token emitted by the ASR to signal the end of a turn.
        sample_rate_hz: Sample rate for incoming audio.
        persona_path: Path to the persona/system prompt file.
        min_vram_gb: Minimum VRAM required to select the larger model.
        model_override: Explicit model name to use instead of auto-selection.
        tool_call_limit: Maximum depth of nested tool calls per turn.
        vibevoice_uri: WebSocket endpoint for the VibeVoice server.
        vibevoice_voice: Optional voice/style identifier to request from VibeVoice.
        flush_on_punctuation: Flush buffered text to TTS when punctuation is detected (dev/burst mode).
        flush_char_threshold: Maximum characters to buffer before forcing a flush in dev mode.
    """

    dev_mode = profile != "prod"

    parakeet_service = ParakeetService(
        server_uri=riva_uri,
        sample_rate_hz=sample_rate_hz,
        end_of_utterance_token=end_of_utterance_token,
        dev_mode=dev_mode,
        dev_buffer_ms=dev_buffer_ms,
        max_buffer_ms=dev_max_buffer_ms,
        initial_prompt=prepend_prompt or None,
    )

    stt_adapter = ParakeetSTTAdapter(
        parakeet_service,
        prepend_prompt=prepend_prompt,
        append_prompt=append_prompt,
    )

    model_router = ModelRouter(persona_path=Path(persona_path), min_vram_gb=min_vram_gb, override_model=model_override)
    system_prompt = model_router.load_persona()
    tool_registry = create_default_registry()
    llm_client = OllamaClient(
        model_router=model_router,
        tool_registry=tool_registry,
        profile=profile,
        system_prompt=system_prompt,
        host=ollama_host,
        tool_call_limit=tool_call_limit,
    )

    vibevoice_service = VibeVoiceService(
        server_uri=vibevoice_uri,
        voice=vibevoice_voice,
        dev_mode=dev_mode,
    )
    tts_adapter = VibeVoiceAdapter(
        vibevoice_service,
        streaming_mode=not dev_mode,
        flush_on_punctuation=flush_on_punctuation,
        flush_char_threshold=flush_char_threshold,
    )

    return Pipeline([
        stt_adapter,
        llm_client,
        tts_adapter,
    ])


def create_stub_pipeline():
    """Alias to the main pipeline for backwards compatibility."""

    return create_pipeline()
