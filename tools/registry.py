"""Tool registry and default tool implementations."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List

import aiohttp

ToolFunc = Callable[..., Awaitable[str]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    function: ToolFunc

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Register and invoke JSON-schema tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._memory: Dict[str, str] = {}
        self._mode: str = "dev"

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def tool_schemas(self) -> List[Dict[str, Any]]:
        return [tool.to_openai_schema() for tool in self._tools.values()]

    async def invoke(self, name: str, arguments: Dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Unknown tool: {name}"
        try:
            return await tool.function(**arguments)
        except TypeError as exc:
            return f"Invalid arguments for {name}: {exc}"
        except Exception as exc:  # pragma: no cover - runtime guard
            return f"Tool {name} failed: {exc}"

    def memory_snapshot(self) -> Dict[str, str]:
        return dict(self._memory)

    def mode(self) -> str:
        return self._mode


async def _web_search(query: str, recency_days: int = 30, max_results: int = 5) -> str:
    if not importlib.util.find_spec("tavily"):
        return "Web search is not configured; install tavily-python and set TAVILY_API_KEY."

    from tavily import TavilyClient  # type: ignore

    client = TavilyClient()
    try:
        results = client.search(query=query, max_results=max_results, days=recency_days)
    except Exception as exc:  # pragma: no cover - external dependency
        return f"Search failed: {exc}"

    if not results or not results.get("results"):
        return "No results found."

    lines = []
    for item in results["results"]:
        title = item.get("title", "result")
        url = item.get("url", "")
        content = item.get("content", "")
        lines.append(f"{title}: {url}\n{content}")
    return "\n\n".join(lines)


async def _fetch_url(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                resp.raise_for_status()
                text = await resp.text()
        except Exception as exc:  # pragma: no cover - network path
            return f"Failed to fetch {url}: {exc}"
    snippet = text.strip()
    if len(snippet) > 2000:
        snippet = snippet[:2000] + "..."
    return snippet


async def _remember(registry: ToolRegistry, key: str, value: str) -> str:
    registry._memory[key] = value
    return f"Remembered {key}."


async def _forget(registry: ToolRegistry, key: str) -> str:
    if key in registry._memory:
        del registry._memory[key]
        return f"Forgot {key}."
    return f"No entry for {key}."


async def _set_mode(registry: ToolRegistry, mode: str) -> str:
    registry._mode = mode
    return f"Switched to {mode} mode."


def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        Tool(
            name="web_search",
            description="Search the web for up-to-date information.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "recency_days": {
                        "type": "integer",
                        "description": "Limit results to the last N days",
                        "default": 30,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            function=_web_search,
        )
    )

    registry.register(
        Tool(
            name="fetch_url",
            description="Retrieve the readable text from a web page for citation.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"],
            },
            function=_fetch_url,
        )
    )

    registry.register(
        Tool(
            name="remember",
            description="Store a fact about the user for later recall.",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key for the memory"},
                    "value": {"type": "string", "description": "Value to remember"},
                },
                "required": ["key", "value"],
            },
            function=lambda key, value, registry=registry: _remember(registry, key, value),
        )
    )

    registry.register(
        Tool(
            name="forget",
            description="Forget a stored fact.",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key for the memory"},
                },
                "required": ["key"],
            },
            function=lambda key, registry=registry: _forget(registry, key),
        )
    )

    registry.register(
        Tool(
            name="set_mode",
            description="Switch between dev and prod profiles at runtime.",
            parameters={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["dev", "prod"],
                        "description": "Target mode",
                    }
                },
                "required": ["mode"],
            },
            function=lambda mode, registry=registry: _set_mode(registry, mode),
        )
    )

    return registry
