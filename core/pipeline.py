"""
Voice agent pipeline wiring using Parakeet for speech recognition.
"""
from pipecat.pipeline.pipeline import Pipeline

from llm.stub_llm_service import StubLLMService
from stt.parakeet_adapter import ParakeetSTTAdapter
from stt.parakeet_service import ParakeetService
from tts.stub_tts_service import StubTTSService


DEFAULT_RIVA_URI = "localhost:50051"


def create_pipeline(
    profile: str = "dev",
    *,
    riva_uri: str = DEFAULT_RIVA_URI,
    prepend_prompt: str = "",
    append_prompt: str = "",
    dev_buffer_ms: int = 2000,
    dev_max_buffer_ms: int = 8000,
    end_of_utterance_token: str = "<EOU>",
    sample_rate_hz: int = 16000,
):
    """Create a pipeline configured for production or development.

    Args:
        profile: Either ``"prod"`` (true streaming) or ``"dev"`` (buffered batches).
        riva_uri: URI of the running Riva server.
        prepend_prompt: Optional text prepended to each transcript.
        append_prompt: Optional text appended to each transcript (e.g., guidance).
        dev_buffer_ms: Buffer window used in development mode before decoding.
        dev_max_buffer_ms: Maximum buffer size in development mode.
        end_of_utterance_token: Token emitted by the ASR to signal the end of a turn.
        sample_rate_hz: Sample rate for incoming audio.
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

    return Pipeline([
        stt_adapter,
        StubLLMService(),
        StubTTSService(),
    ])


def create_stub_pipeline():
    """Alias to the main pipeline for backwards compatibility."""

    return create_pipeline()
