import asyncio
import contextlib
import json
import sys
from pathlib import Path
from typing import List, Tuple

import pytest
from pipecat.frames.frames import InterruptionFrame, TextFrame
from pipecat.processors.frame_processor import FrameDirection

sys.path.append(str(Path(__file__).resolve().parents[1]))

from llm.model_router import ModelRouter
from llm.stub_llm_service import StubLLMService, StubResponse
from stt.parakeet_adapter import EndOfUtteranceFrame
from tools.registry import Tool, ToolRegistry


async def _capture_frames(service: StubLLMService) -> List[Tuple[TextFrame, FrameDirection]]:
    captured: List[Tuple[TextFrame, FrameDirection]] = []

    class InlineTaskManager:
        def create_task(self, coroutine, name=None):
            return asyncio.create_task(coroutine, name=name)

        async def wait_for_task(self, task):
            return await task

        async def cancel_task(self, task, timeout=None):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    service._task_manager = InlineTaskManager()  # type: ignore[attr-defined]

    async def _push(frame, direction):
        captured.append((frame, direction))

    service.push_frame = _push  # type: ignore[assignment]
    return captured


async def _await_generation(service: StubLLMService, attempts: int = 20, delay: float = 0.05):
    for _ in range(attempts):
        task = service._generation_task  # type: ignore[attr-defined]
        if task is None:
            return
        if task.done():
            with contextlib.suppress(Exception):
                await task
            return
        await asyncio.sleep(delay)
    raise TimeoutError("Generation task did not complete in time")


def test_stub_llm_uses_persona_as_default_system_prompt():
    asyncio.run(_run_persona_test())


async def _run_persona_test():
    router = ModelRouter(persona_path=Path("config/persona_default.md"))
    registry = ToolRegistry()
    responses = [StubResponse(tokens=["Hello! "])]
    service = StubLLMService(router, registry, responses=responses)
    captured = await _capture_frames(service)

    await service.process_frame(TextFrame("hi"), FrameDirection.DOWNSTREAM)
    await service.process_frame(EndOfUtteranceFrame(), FrameDirection.DOWNSTREAM)
    await _await_generation(service)

    assert service._messages[0]["role"] == "system"
    assert service._messages[0]["content"] == router.load_persona()
    assert isinstance(captured[0][0], TextFrame)
    assert captured[0][0].text == "Hello! "


def test_stub_llm_allows_system_prompt_override():
    asyncio.run(_run_override_test())


async def _run_override_test():
    router = ModelRouter()
    registry = ToolRegistry()
    responses = [StubResponse(tokens=["Hi there"])]
    custom_prompt = "custom system prompt"
    service = StubLLMService(
        router,
        registry,
        responses=responses,
        system_prompt=custom_prompt,
    )
    await _capture_frames(service)

    await service.process_frame(TextFrame("hi"), FrameDirection.DOWNSTREAM)
    await service.process_frame(EndOfUtteranceFrame(), FrameDirection.DOWNSTREAM)
    await _await_generation(service)

    assert service._messages[0] == {"role": "system", "content": custom_prompt}


def test_stub_llm_respects_tool_call_limit():
    asyncio.run(_run_tool_limit_test())


async def _run_tool_limit_test():
    router = ModelRouter()
    registry = ToolRegistry()
    tool_call_counter = 0

    async def echo(text: str):
        nonlocal tool_call_counter
        tool_call_counter += 1
        return f"echo: {text}"

    registry.register(
        Tool(
            name="echo",
            description="Echo back text",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            function=echo,
        )
    )

    responses = [
        StubResponse(
            tool_calls=[
                {
                    "id": "call_1",
                    "function": {"name": "echo", "arguments": json.dumps({"text": "first"})},
                }
            ]
        ),
        StubResponse(
            tool_calls=[
                {
                    "id": "call_2",
                    "function": {"name": "echo", "arguments": json.dumps({"text": "second"})},
                }
            ]
        ),
    ]

    service = StubLLMService(router, registry, responses=responses, tool_call_limit=1)
    captured = await _capture_frames(service)

    await service.process_frame(TextFrame("hi"), FrameDirection.DOWNSTREAM)
    await service.process_frame(EndOfUtteranceFrame(), FrameDirection.DOWNSTREAM)
    await _await_generation(service)

    assert tool_call_counter == 1
    assert any(
        "unable to complete further tool calls" in frame.text for frame, _ in captured if isinstance(frame, TextFrame)
    )


def test_interruption_cancels_streaming():
    asyncio.run(_run_interruption_test())


async def _run_interruption_test():
    router = ModelRouter()
    registry = ToolRegistry()
    responses = [StubResponse(tokens=list("streaming tokens"))]
    service = StubLLMService(router, registry, responses=responses, token_delay=0.05)
    captured = await _capture_frames(service)

    await service.process_frame(TextFrame("hello"), FrameDirection.DOWNSTREAM)
    await service.process_frame(EndOfUtteranceFrame(), FrameDirection.DOWNSTREAM)
    await asyncio.sleep(0.06)
    await service.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)

    assert service._generation_task is None
    assert len(captured) < len("streaming tokens")
