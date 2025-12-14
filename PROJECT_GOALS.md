# Project Goals and Roadmap

This document summarises the objectives of the **Local‑Call Voice Agent** and
provides a rough roadmap for implementation.  The vision is to build an
open, extensible platform for real‑time voice assistants that can operate
locally on commodity hardware.

## Objectives

1. **End‑to‑end voice pipeline** – Assemble a streaming pipeline comprising
   speech‑to‑text, language model and text‑to‑speech services.  Each
   component should communicate over frames and support streaming and
   cancellation to enable barge‑in and low‑latency responses.

2. **Tool‑calling agent** – Enable the language model to call arbitrary
   functions via JSON schemas.  This includes web search, URL fetching,
   calculator operations and memory manipulation.  Tools should be
   modular and easy to register.

3. **Persona and memory** – Implement a persistent persona that defines
   tone, style and conversation policy.  Provide a memory store so the
   assistant can remember facts about the user across sessions.

4. **Profile support** – Provide separate profiles for development (CPU)
   and production (GPU).  Development mode should be tolerant of slow
   inference by buffering STT and TTS, while production mode targets
   real‑time latency.

5. **Extensibility** – Make it straightforward to swap out STT, LLM or
   TTS services, add new tools, or change the transport (e.g. WebRTC,
   telephony).  Use Pipecat’s modular pipeline design to isolate each
   component【11390798207545†L107-L130】.

6. **Documentation and examples** – Provide clear documentation for
   developers and end users, including setup instructions, code examples,
   persona guidelines and tool templates.

## Roadmap

1. **Initial scaffolding**
   - Create repository structure (done).
   - Implement core pipeline classes (`core/pipeline.py`, `core/session.py`) (done).
   - Provide stub adapters for STT, LLM and TTS with dummy data so that
     the pipeline can be exercised without models (done).

2. **Integrate Parakeet STT**
   - Implement `stt/parakeet_service.py` to run Parakeet offline using
     NeMo or Riva.
   - Implement `stt/parakeet_adapter.py` for Pipecat to convert audio
     frames to transcripts and detect `<EOU>`【432627428859135†L69-L73】.
   - Implement buffered mode for development.

3. **Integrate Ollama LLM**
   - Implement `llm/ollama_client.py` to stream chat completions and
     handle tool calls.
   - Implement `llm/model_router.py` to select the appropriate model
     (Qwen3 vs. Gemma2) based on profile and VRAM.
   - Define basic tools in `tools/registry.py`.

4. **Integrate VibeVoice TTS**
   - Implement `tts/vibevoice_service.py` to speak text via the
     WebSocket server【620260211077025†L63-L92】.
   - Implement `tts/vibevoice_adapter.py` for streaming and burst modes.

5. **Client and transport**
   - Implement `ui/websocket_transport.py` to stream audio to/from a
     browser client.
   - Add optional WebRTC transport for lower latency.

6. **Advanced features**
   - Add barge‑in logic to cancel TTS and LLM mid‑generation when the
     user starts speaking again.
   - Implement memory store using DuckDB and expose `remember`/
     `forget` tools.
   - Support persona switching and editing.

7. **Polishing**
   - Add logging, metrics and error handling.
   - Provide tests and sample scripts.
   - Optimise resource governor for single‑GPU setups.

This roadmap is aspirational; contributions and deviations are welcome!