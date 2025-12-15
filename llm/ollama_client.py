"""Ollama-backed chat completion client with streaming and tool support."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ollama import AsyncClient
from pipecat.frames.frames import Frame, TextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from llm.model_router import ModelRouter
from stt.parakeet_adapter import EndOfUtteranceFrame
from tools.registry import ToolRegistry


class OllamaClient(FrameProcessor):
    """Stream chat completions from Ollama and handle OpenAI-style tool calls."""

    def __init__(
        self,
        model_router: ModelRouter,
        tool_registry: ToolRegistry,
        *,
        profile: str = "dev",
        system_prompt: Optional[str] = None,
        host: str = "http://localhost:11434",
        tool_call_limit: int = 3,
    ) -> None:
        super().__init__()
        self._model_router = model_router
        self._tool_registry = tool_registry
        self._profile = profile
        self._tool_call_limit = tool_call_limit
        self._client = AsyncClient(host=host)
        self._messages: List[Dict[str, Any]] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})
        self._pending_user: List[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, TextFrame):
            self._pending_user.append(frame.text)
            return

        if isinstance(frame, EndOfUtteranceFrame):
            text = " ".join(self._pending_user).strip()
            self._pending_user.clear()
            if text:
                await self._handle_user_turn(text)
            return

        await self.push_frame(frame, direction)

    async def _handle_user_turn(self, text: str):
        self._messages.append({"role": "user", "content": text})
        await self._run_chat_with_tools(depth=0)

    async def _run_chat_with_tools(self, *, depth: int):
        model = self._model_router.select_model(self._profile)
        tools = self._tool_registry.tool_schemas()
        tool_calls, assistant_content = await self._stream_completion(model, tools)
        if tool_calls:
            assistant_message = {
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": tool_calls,
            }
            self._messages.append(assistant_message)
            if depth >= self._tool_call_limit:
                await self.push_frame(
                    TextFrame("I'm unable to complete further tool calls right now."),
                    FrameDirection.DOWNSTREAM,
                )
                return
            await self._process_tool_calls(tool_calls)
            await self._run_chat_with_tools(depth=depth + 1)
        elif assistant_content:
            self._messages.append({"role": "assistant", "content": assistant_content})

    async def _stream_completion(self, model: str, tools: List[Dict[str, Any]]):
        tool_calls: List[Dict[str, Any]] = []
        content_fragments: List[str] = []
        async for chunk in self._client.chat(
            model=model,
            messages=self._messages,
            tools=tools if tools else None,
            stream=True,
        ):
            message = chunk.get("message", {})
            delta = message.get("content")
            if delta:
                content_fragments.append(delta)
                await self.push_frame(TextFrame(delta), FrameDirection.DOWNSTREAM)
            chunk_tool_calls = message.get("tool_calls") or []
            if chunk_tool_calls:
                tool_calls.extend(chunk_tool_calls)
        assistant_content = "".join(content_fragments).strip()
        return tool_calls, assistant_content

    async def _process_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        for call in tool_calls:
            function = call.get("function", {})
            name = function.get("name")
            raw_arguments = function.get("arguments", "{}")
            args = self._safe_json_loads(raw_arguments)
            result = await self._tool_registry.invoke(name or "", args)
            tool_message: Dict[str, Any] = {
                "role": "tool",
                "tool_call_id": call.get("id"),
                "name": name,
                "content": result,
            }
            self._messages.append(tool_message)

    @staticmethod
    def _safe_json_loads(payload: str) -> Dict[str, Any]:
        try:
            loaded = json.loads(payload)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass
        return {}

    async def aclose(self):
        await self._client.close()

    async def cleanup(self):
        await self.aclose()

