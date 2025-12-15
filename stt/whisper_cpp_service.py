
import aiohttp
from typing import AsyncIterator

class WhisperCPPService:
    def __init__(self, server_url: str):
        self._server_url = server_url

    async def stream_transcription(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        async with aiohttp.ClientSession() as session:
            async for chunk in audio_stream:
                async with session.post(self._server_url, data=chunk) as response:
                    if response.status == 200:
                        result = await response.json()
                        yield result.get("text", "")
                    else:
                        yield ""
