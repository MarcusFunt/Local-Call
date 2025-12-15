
"""Stub LLM service that reuses :class:`OllamaClient` logic for testing."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional

from pipecat.frames.frames import TextFrame
from pipecat.processors.frame_processor import FrameDirection

from llm.model_router import ModelRouter
from llm.ollama_client import OllamaClient
from tools.registry import ToolRegistry


@dataclass
class StubResponse:
    """Pre-scripted response returned by :class:`StubLLMService`."""

    tokens: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


class StubLLMService(OllamaClient):
    """
    A drop-in replacement for :class:`OllamaClient` that feeds canned responses.

    The service inherits all turn-handling behaviour from ``OllamaClient``:
    - It buffers ``TextFrame`` content until an ``EndOfUtteranceFrame`` arrives.
    - It routes the request through :class:`~llm.model_router.ModelRouter` to
      select a model for the active profile.
    - It streams assistant tokens downstream and executes tool calls via the
      provided :class:`~tools.registry.ToolRegistry`.
    - ``InterruptionFrame`` instances cancel any in-flight generation task.
    """

    def __init__(
        self,
        model_router: ModelRouter,
        tool_registry: ToolRegistry,
        *,
        responses: Iterable[StubResponse],
        profile: str = "dev",
        system_prompt: Optional[str] = None,
        token_delay: float = 0.0,
        tool_call_limit: int = 3,
    ) -> None:
        prompt = system_prompt if system_prompt is not None else model_router.load_persona()
        super().__init__(
            model_router,
            tool_registry,
            profile=profile,
            system_prompt=prompt,
            host="http://localhost:0",  # Unused; no real network calls in the stub
            tool_call_limit=tool_call_limit,
        )
        self._responses: Iterator[StubResponse] = iter(responses)
        self._token_delay = token_delay

    async def _stream_completion(self, model: str, tools: List[Dict[str, Any]]):  # type: ignore[override]
        try:
            response = next(self._responses)
        except StopIteration:
            return [], ""

        tool_calls = list(response.tool_calls or [])
        fragments: List[str] = []
        try:
            for token in response.tokens:
                fragments.append(token)
                await self.push_frame(TextFrame(token), FrameDirection.DOWNSTREAM)
                if self._token_delay:
                    await asyncio.sleep(self._token_delay)
                else:
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            raise

        return tool_calls, "".join(fragments).strip()
