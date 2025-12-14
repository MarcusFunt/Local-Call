
"""
This module defines the main voice agent pipeline.
The pipeline is responsible for processing audio from the user,
generating a response, and converting the response to audio.
"""
from pipecat.pipeline.pipeline import Pipeline
from stt.stub_stt_service import StubSTTService
from llm.stub_llm_service import StubLLMService
from tts.stub_tts_service import StubTTSService

def create_stub_pipeline():
    """
    Creates a pipeline with stub services for STT, LLM, and TTS.
    This is useful for testing the basic pipeline structure without
    requiring actual models to be loaded.
    """
    return Pipeline([
        # The STT service transcribes audio from the user into text.
        StubSTTService(),
        # The LLM service takes the transcribed text and generates a response.
        StubLLMService(),
        # The TTS service converts the response text into audio.
        StubTTSService(),
    ])
