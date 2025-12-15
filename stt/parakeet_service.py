"""
Service wrapper for running NVIDIA Parakeet (via NeMo / Riva) in streaming or
buffered modes.

The class exposes a single coroutine, :meth:`stream_transcription`, which takes
an async iterator of raw PCM audio chunks and yields :class:`TranscriptSegment`
objects containing partial transcripts.  End-of-utterance (``<EOU>``) tokens are
stripped from the emitted text while still signalling ``end_of_utterance`` to
callers.

In production the service relays audio to a running Riva ASR instance and
streams interim results.  Development mode uses a configurable buffer to batch
chunks before sending them to the recogniser (useful when running on CPU where
real-time streaming is unrealistic).
"""
from __future__ import annotations

import asyncio
import queue
import threading
from dataclasses import dataclass
from typing import AsyncIterator, Iterator, List, Optional


@dataclass
class TranscriptSegment:
    """Container for a single transcript fragment."""

    text: str
    is_final: bool
    end_of_utterance: bool = False


class ParakeetService:
    """Wrapper around the Parakeet ASR model served via Riva."""

    def __init__(
        self,
        server_uri: str = "localhost:50051",
        *,
        use_ssl: bool = False,
        ssl_cert: Optional[str] = None,
        metadata: Optional[List[str]] = None,
        language_code: str = "en-US",
        sample_rate_hz: int = 16000,
        chunk_ms: int = 80,
        end_of_utterance_token: str = "<EOU>",
        initial_prompt: Optional[str] = None,
        dev_mode: bool = False,
        dev_buffer_ms: int = 2000,
        max_buffer_ms: int = 8000,
    ) -> None:
        self._server_uri = server_uri
        self._use_ssl = use_ssl
        self._ssl_cert = ssl_cert
        self._metadata = metadata or []
        self._language_code = language_code
        self._sample_rate_hz = sample_rate_hz
        self._chunk_ms = chunk_ms
        self._end_of_utterance_token = end_of_utterance_token
        self._initial_prompt = initial_prompt
        self._dev_mode = dev_mode
        self._dev_buffer_ms = dev_buffer_ms
        self._max_buffer_ms = max_buffer_ms

        self._auth = None
        self._asr_service = None

    def _ensure_riva(self):
        """Lazy-import Riva and construct the service client."""

        if self._asr_service:
            return

        import importlib

        if not importlib.util.find_spec("riva.client"):
            raise RuntimeError(
                "riva.client is required to run Parakeet. Install NVIDIA Riva "
                "client or run against a Riva server."
            )

        riva = importlib.import_module("riva.client")  # type: ignore

        self._auth = riva.Auth(  # type: ignore
            uri=self._server_uri, use_ssl=self._use_ssl, ssl_cert=self._ssl_cert, metadata=self._metadata
        )
        self._asr_service = riva.ASRService(self._auth)  # type: ignore

    def _build_recognition_config(self):
        import importlib

        riva = importlib.import_module("riva.client")  # type: ignore

        return riva.RecognitionConfig(  # type: ignore
            encoding=riva.AudioEncoding.LINEAR_PCM,  # type: ignore
            sample_rate_hz=self._sample_rate_hz,
            language_code=self._language_code,
            max_alternatives=1,
            enable_automatic_punctuation=False,
            verbatim_transcripts=True,
        )

    def _build_streaming_config(self):
        import importlib

        cfg = self._build_recognition_config()
        custom_configuration = {}
        if self._initial_prompt:
            custom_configuration["prompt"] = self._initial_prompt
        riva = importlib.import_module("riva.client")  # type: ignore

        return riva.StreamingRecognitionConfig(  # type: ignore
            config=cfg, interim_results=True, enable_word_time_offsets=False, custom_configuration=custom_configuration
        )

    def _decode_response(self, response) -> Iterator[TranscriptSegment]:
        # Riva responses contain a list of results, each with alternatives.
        for result in getattr(response, "results", []):
            if not getattr(result, "alternatives", None):
                continue
            alternative = result.alternatives[0]
            text = getattr(alternative, "transcript", "")
            end_of_utterance = False
            if self._end_of_utterance_token and self._end_of_utterance_token in text:
                end_of_utterance = True
                text = text.replace(self._end_of_utterance_token, "").strip()
            yield TranscriptSegment(text=text, is_final=getattr(result, "is_final", False) or end_of_utterance, end_of_utterance=end_of_utterance)

    def _stream_with_riva(
        self, audio_generator: Iterator[bytes]
    ) -> Iterator[TranscriptSegment]:  # pragma: no cover - integration path
        self._ensure_riva()
        import riva.client  # type: ignore

        config = self._build_streaming_config()
        responses = self._asr_service.streaming_response_generator(  # type: ignore
            config=config,
            audio_chunks=audio_generator,
            fill_buffers=False,
        )
        for response in responses:
            yield from self._decode_response(response)

    def _offline_recognize(self, audio_buffer: bytes) -> List[TranscriptSegment]:  # pragma: no cover - integration path
        self._ensure_riva()
        config = self._build_recognition_config()
        if self._initial_prompt:
            config.custom_configuration = {"prompt": self._initial_prompt}  # type: ignore
        response = self._asr_service.offline_recognize(config, audio_buffer)  # type: ignore
        return list(self._decode_response(response))

    async def _run_streaming(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[TranscriptSegment]:
        loop = asyncio.get_running_loop()
        audio_queue: queue.Queue[Optional[bytes]] = queue.Queue()
        segment_queue: asyncio.Queue[Optional[TranscriptSegment]] = asyncio.Queue()
        done_sending = threading.Event()

        async def forward_audio():
            async for chunk in audio_stream:
                audio_queue.put(chunk)
            done_sending.set()

        async def forward_segments():
            while True:
                segment = await segment_queue.get()
                if segment is None:
                    break
                yield segment

        def audio_generator():
            while not (done_sending.is_set() and audio_queue.empty()):
                try:
                    chunk = audio_queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                if chunk is None:
                    break
                yield chunk

        def worker():
            try:
                for segment in self._stream_with_riva(audio_generator()):
                    asyncio.run_coroutine_threadsafe(segment_queue.put(segment), loop)
            finally:
                asyncio.run_coroutine_threadsafe(segment_queue.put(None), loop)

        audio_task = asyncio.create_task(forward_audio())
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        async for segment in forward_segments():
            yield segment

        await audio_task
        thread.join()

    async def _run_buffered(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[TranscriptSegment]:
        buffer = bytearray()

        def buffer_ms() -> float:
            # 2 bytes per sample for 16-bit PCM
            return (len(buffer) / (self._sample_rate_hz * 2)) * 1000

        async for chunk in audio_stream:
            buffer.extend(chunk)
            if buffer_ms() >= self._dev_buffer_ms or buffer_ms() >= self._max_buffer_ms:
                segments = self._offline_recognize(bytes(buffer))
                buffer.clear()
                for segment in segments:
                    yield segment

        if buffer:
            segments = self._offline_recognize(bytes(buffer))
            for segment in segments:
                yield segment

    async def stream_transcription(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[TranscriptSegment]:
        """Yield transcript segments for a stream of audio chunks."""

        if self._dev_mode:
            async for segment in self._run_buffered(audio_stream):
                yield segment
        else:
            async for segment in self._run_streaming(audio_stream):
                yield segment
