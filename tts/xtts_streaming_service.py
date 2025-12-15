
import aiohttp
from typing import AsyncIterator

class XTTSStreamingService:
    def __init__(self, server_url: str):
        self._server_url = server_url

    async def stream_synthesis(self, text_stream: AsyncIterator[str]) -> AsyncIterator[bytes]:
        async with aiohttp.ClientSession() as session:
            async for text in text_stream:
                params = {"text": text}
                async with session.get(self._server_url, params=params) as response:
                    if response.status == 200:
                        async for chunk in response.content.iter_any():
                            yield chunk
                    else:
                        yield b""
