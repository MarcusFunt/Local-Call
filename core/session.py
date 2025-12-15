
"""Session lifecycle management for the voice pipeline."""

from __future__ import annotations

from typing import Optional

from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask

from core.pipeline import create_stub_pipeline


class Session:
    """Manage the lifecycle of a single conversational session."""

    def __init__(self, transport, profile) -> None:
        self.transport = transport
        self.profile = profile
        self.pipeline_task: Optional[PipelineTask] = None
        self.runner: Optional[PipelineRunner] = None

    async def start(self):
        """Starts the configured voice agent pipeline."""

        pipeline = create_stub_pipeline(self.profile, self.transport)
        self.pipeline_task = PipelineTask(pipeline)
        self.runner = PipelineRunner()
        await self.runner.run(self.pipeline_task)

    async def stop(self):
        """Stop the pipeline and clean up resources."""

        if self.runner:
            await self.runner.cancel()
        self.runner = None
        self.pipeline_task = None
