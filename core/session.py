
"""
This module defines the Session class, which manages the lifecycle of a
voice agent pipeline.
"""
import asyncio
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from core.pipeline import create_stub_pipeline

class Session:
    """
    The Session class manages the lifecycle of a voice agent pipeline.
    It is responsible for starting and stopping the pipeline, and for
    handling the transport of audio and text frames between the client
    and the server.
    """

    def __init__(self, transport):
        """
        Initializes a new Session object.

        Args:
            transport: The transport to use for sending and receiving frames.
        """
        self.transport = transport
        self.pipeline_task = None
        self.runner = None

    async def start(self):
        """
        Starts the voice agent pipeline.
        """
        self.runner = PipelineRunner()
        self.pipeline_task = PipelineTask(
            create_stub_pipeline(),
            self.transport.input(),
            self.transport.output()
        )
        await self.runner.run(self.pipeline_task)

    async def stop(self):
        """
        Stops the voice agent pipeline.
        """
        if self.runner:
            await self.runner.stop()
            self.runner = None
            self.pipeline_task = None
