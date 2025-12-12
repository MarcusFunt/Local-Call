# Agents and Services

This document breaks down the major components of the Local‑Call voice agent.  Each
service is designed to be modular so that it can be replaced or extended without
touching the rest of the pipeline.  You can view the runtime wiring in
`core/pipeline.py` and adaptors in the `stt/`, `llm/` and `tts/` packages.

## Speech‑to‑Text (STT)

**Model:** `nvidia/parakeet_realtime_eou_120m-v1`  
**Framework:** NVIDIA NeMo / Riva

Parakeet‑Realtime‑EOU‑120 M is a low‑latency streaming ASR model that outputs
plain text and emits a `<EOU>` token at the end of each utterance【432627428859135†L69-L73】.  This
token allows the pipeline to determine when the user has finished speaking and to
stop buffering audio.  Key properties:

- **Latency:** 80–160 ms【432627428859135†L69-L73】.
- **Language:** English only.  It does not output punctuation or capitalisation; the
  language model must infer sentence boundaries.
- **Input format:** 16 kHz mono audio【432627428859135†L114-L119】.
- **Integration:** Run as a separate service (e.g. via NeMo’s streaming server) or
  load directly in `stt/parakeet_service.py`.  The Pipecat adapter
  `ParakeetSTTAdapter` chunks audio into 80 ms frames and forwards partial
  transcriptions as they arrive.  When `<EOU>` is detected the adapter emits a
  `FinalTranscriptFrame` to end the turn.

### Development mode

On CPU, real‑time decoding is impractical.  The `dev` profile switches the
adapter to a buffered mode: it collects audio for a configurable window
(e.g. 2 s), runs a batch decode and emits a partial transcript.  The
`max_buffer_ms` field prevents runaway buffering.  Development mode also
emits `<EOU>` when silence is detected to simulate end‑of‑turn behaviour.

## Language Model (LLM)

**Models:** `qwen3:14b` (production), `gemma2:2b` (development)  
**Framework:** Ollama via its OpenAI‑compatible API

The LLM is the brain of the agent.  It receives the user’s transcript and the
conversation context, decides whether to call tools and streams tokens for the
assistant’s reply.  We support two models:

- **Qwen3‑14 B** – A state‑of‑the‑art reasoning model with support for function
  calling.  When run at 4‑bit quantisation it fits in 12 GB of GPU VRAM and
  provides sufficient context length for conversation and web search results.
- **Gemma2‑2 B** – A smaller model used for development and fallback.  It is
  fast enough to run on CPU and still supports the same function calling
  interface.  In development mode the resource governor automatically
  switches to Gemma when GPU VRAM is insufficient.

### Tool‑Calling

The LLM is configured with a list of JSON‑schema tools.  When the model
predicts that a function should be invoked, Pipecat intercepts the call,
executes your Python handler and feeds the result back into the LLM context.

Built‑in tools include:

| Tool name | Description |
|---|---|
| `web_search(query, recency_days=30, max_results=5)` | Use Tavily or another search API to find relevant web pages. |
| `fetch_url(url)` | Retrieve the readable text from a web page for citation. |
| `remember(key, value)` / `forget(key)` | Store and recall facts about the user. |
| `set_mode(mode)` | Switch between `dev` and `prod` profiles at runtime. |

You can register additional tools in `tools/registry.py`.  Each tool exposes a
JSON schema for its arguments and a Python handler that returns a string
result.

### Persona and Memory

The LLM uses a **system prompt** derived from your persona file in
`config/persona_default.md`.  The persona defines tone, politeness, topic
boundaries and style guidelines.  It may also include hard‑coded facts about
the user.  A memory store in `agent/memory_store.py` persists facts learned
through the `remember` tool.

## Text‑to‑Speech (TTS)

**Model:** `VibeVoice‑Realtime‑0.5B`  
**Framework:** VibeVoice server (open‑source) or other TTS service

VibeVoice is a lightweight, real‑time TTS model capable of streaming audio
as soon as it receives the first tokens【620260211077025†L63-L67】.  It uses an interleaved,
windowed design to encode incoming text chunks while simultaneously decoding
audio【620260211077025†L79-L84】.  Key properties:

- **Latency:** Initial audible speech within ~300 ms (hardware dependent)【620260211077025†L63-L67】.
- **Parameter size:** 0.5 billion parameters (deployment friendly)【620260211077025†L86-L88】.
- **Streaming input:** Accepts text in small increments; works well with LLM
  token streaming【620260211077025†L63-L92】.
- **Language:** Primarily English; additional languages may work but are not
  guaranteed【620260211077025†L73-L98】.

### Development mode

On CPU the adapter switches to **burst‑TTS** mode: it collects generated tokens
until it hits punctuation or a character threshold, sends the batch to the
TTS service, streams the resulting audio and then clears the buffer.  The
`flush_on_punctuation` and `flush_char_threshold` options control this behaviour.

## Pipeline and Turn Management

The overall pipeline is assembled as follows【11390798207545†L107-L130】:

```python
pipeline = Pipeline([
    transport.input(),    # mic audio
    stt,                  # speech‑to‑text (Parakeet)
    context.user(),       # update conversation history
    llm,                  # reason over the transcript and decide on tools
    tts,                  # synthesize assistant speech (VibeVoice)
    transport.output(),   # play audio back to the user
    context.assistant(),  # update history with assistant response
])
```

When the user starts speaking, a `UserStartedSpeakingFrame` is emitted.  As
transcripts come in, the LLM may begin generating tokens before the full
sentence is finished.  If the user interrupts while the assistant is speaking,
a `StartInterruptionFrame` triggers cancellation: the TTS is cancelled,
LLM generation is interrupted, and the STT begins capturing the new utterance.

## Adding Your Own Components

The modular architecture makes it straightforward to extend the agent:

* **Swap STT/TTS**:  Implement a new service wrapper in `stt/` or `tts/` and
  a Pipecat adapter class.  Register it in your profile YAML.
* **New tools**:  Define a function with a JSON schema and register it in
  `tools/registry.py`.  The LLM will automatically learn to call it.
* **Alternate LLMs**:  Provided the model supports OpenAI function calling and
  streaming, you can point the `model_router` at any local or remote
  endpoint.  Set `model` in your profile accordingly.

For more details see the code comments in each module and read the
Pipecat documentation on [frame processors](https://docs.pipecat.ai/guides/learn/pipeline).