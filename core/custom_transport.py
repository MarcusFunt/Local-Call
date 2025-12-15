
import base64
import json
from pipecat.frames.frames import AudioFrame, Frame, TextFrame
from pipecat.transports.websocket_transport import WebsocketTransport

class JSONWebsocketTransport(WebsocketTransport):
    async def _send_frame(self, frame: Frame):
        if isinstance(frame, TextFrame):
            await self._websocket.send_text(json.dumps({"type": "transcript", "text": frame.text}))
        elif isinstance(frame, AudioFrame):
            encoded_audio = base64.b64encode(frame.audio).decode("utf-8")
            await self._websocket.send_text(json.dumps({"type": "audio", "audio": encoded_audio}))
        else:
            pass
