"""
Stub Speech-to-Text service that reuses the Parakeet adapter.

This implementation delegates to :class:`ParakeetSTTAdapter` so that the
pipeline exercises the same `<EOU>` handling as the production STT path.
You can provide a real :class:`ParakeetService` instance or rely on the
included mock that emits transcripts containing the end-of-utterance token.
"""
from __future__ import annotations

from typing import AsyncIterator, Iterable, Optional, Sequence

from pipecat.processors.frame_processor import FrameProcessor

from stt.parakeet_adapter import ParakeetSTTAdapter
from stt.parakeet_service import ParakeetService, TranscriptSegment


class _MockParakeetService:
    """Lightweight mock that emits provided transcripts and `<EOU>` markers."""

    def __init__(
        self,
        transcripts: Optional[Sequence[str]] = None,
        *,
        end_of_utterance_token: str = "<EOU>",
    ) -> None:
        self._transcripts = list(transcripts or ["mock transcript <EOU>"])
        self._end_of_utterance_token = end_of_utterance_token

    async def stream_transcription(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[TranscriptSegment]:
        # Drain the audio generator so the adapter can flush the stream.
        async for _ in audio_stream:
            pass

        for text in self._transcripts:
            cleaned = text
            end_of_utterance = False
            if self._end_of_utterance_token and self._end_of_utterance_token in text:
                end_of_utterance = True
                cleaned = text.replace(self._end_of_utterance_token, "").strip()
            yield TranscriptSegment(text=cleaned, is_final=True, end_of_utterance=end_of_utterance)


class StubSTTService(ParakeetSTTAdapter):
    """Stub that shares the Parakeet adapter code path for tests and demos."""

    def __init__(
        self,
        *,
        service: Optional[ParakeetService] = None,
        transcripts: Optional[Iterable[str]] = None,
        prepend_prompt: str = "",
        append_prompt: str = "",
        end_of_utterance_token: str = "<EOU>",
    ) -> None:
        mock_service = _MockParakeetService(transcripts, end_of_utterance_token=end_of_utterance_token)
        super().__init__(
            service or mock_service,
            prepend_prompt=prepend_prompt,
            append_prompt=append_prompt,
        )

        # Keep a reference so callers can introspect or extend the underlying processor.
        self._delegate: FrameProcessor = service or mock_service
