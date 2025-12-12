# Local Call Voice Agent

This repository contains an experimental **fully local voice‑chat AI agent** that runs on a single
consumer GPU (or entirely on CPU for testing).  It combines a streaming speech‑to‑text (STT)
model, a large language model with tool‑calling capabilities, and a streaming text‑to‑speech (TTS)
model into a single Pipecat pipeline.  The goal is to provide a responsive, real‑time voice
assistant that can search the web, call custom functions, maintain a persona, and speak back
its responses—all without sending user audio to third‑party cloud services.

## Why another voice agent?

Many voice assistants rely on cloud APIs for transcription, reasoning and speech synthesis.
This project demonstrates that you can achieve a similar experience on your own machine.  It
uses **NVIDIA’s Parakeet‑Realtime‑EOU‑120 M** model for low‑latency ASR, which emits a special
`<EOU>` token to mark the end of each utterance and provides no punctuation or capitalization【432627428859135†L69-L73】.
For speech synthesis it uses **Microsoft’s VibeVoice‑Realtime‑0.5 B** model, a lightweight TTS
that supports streaming text input and produces audible speech in roughly 300 ms【620260211077025†L63-L67】.  A local
LLM (Qwen3‑14 B or Gemma2‑2 B) running through the Ollama interface handles reasoning and
tool calls, and Pipecat orchestrates the entire flow as a series of frame processors【11390798207545†L107-L130】.

## Features

- **Streaming voice chat**:  User audio is transcribed in real time by Parakeet.  The end of an
  utterance is detected via the `<EOU>` token, and the assistant begins generating a reply
  immediately.
- **Tool‑calling agent**:  The LLM is configured to call JSON‑schema functions.  Built‑in
  tools include web search, URL fetching, notes/memory and utility functions.  You can
  implement additional tools easily by registering Python callables.
- **Custom persona and memory**:  A persistent persona file defines the assistant’s tone,
  allowed topics and style.  Memory tools allow the assistant to store and recall facts about
  the user.
- **Dev vs. production profiles**:  Development mode runs everything on CPU with relaxed
  timing, buffering STT/TTS in batches.  Production mode uses your GPU for all models to
  achieve minimal latency.
- **Modular pipeline**:  Each service (STT, LLM, TTS) runs as its own service or process.  You
  can swap out components (e.g. use a different TTS) without changing the rest of the
  pipeline.

## Architecture

The agent is built around a Pipecat `Pipeline` with the following processors【11390798207545†L107-L130】:

1. **Transport input** – captures microphone audio frames.
2. **Speech‑to‑text** – feeds audio chunks into Parakeet for streaming transcription.  When
   Parakeet emits `<EOU>` the current utterance is closed and sent to the LLM.
3. **Context aggregator** – updates conversation history and passes user text to the LLM.
4. **Language model** – Qwen3‑14 B or Gemma2‑2 B running via Ollama generates tokens, chooses
   tools and streams text frames to TTS.
5. **Text‑to‑speech** – VibeVoice synthesizes the assistant’s response from streaming tokens【620260211077025†L63-L92】.
6. **Transport output** – plays audio back to the user and handles barge‑in logic (interruptions
   cancel current speech and resume listening).

Each processor communicates with its neighbours via frames—data containers that carry audio,
text or control signals through the pipeline【11390798207545†L144-L175】.  This design allows you to
add processors (e.g. profanity filters or emotion detectors) without rewriting the rest of
the code.

## Installation

### Prerequisites

* Python 3.9+ (tested on 3.11)
* A GPU with at least 12 GB of VRAM for production mode (an RTX 3060 12 GB is
  sufficient), or enough CPU and RAM for development mode.
* [Ollama](https://github.com/ollama/ollama) installed locally with the Qwen3 14 B
  and Gemma2 2 B models pulled (e.g. `ollama pull qwen3:14b` and `ollama pull gemma2:2b`).
* [NVIDIA NeMo toolkit](https://docs.nvidia.com) for Parakeet streaming if you want to
  run the STT model offline.  See the Parakeet model card for installation details【432627428859135†L144-L159】.
* [VibeVoice Realtime 0.5 B](https://github.com/microsoft/VibeVoice) running as a local
  service.  The Hugging Face model card includes a WebSocket example【620260211077025†L63-L71】.

### Setup

1. Clone this repository and create a virtual environment:

   ```bash
   git clone https://github.com/MarcusFunt/Local-Call.git
   cd Local-Call
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure profiles in `config/profiles/`.  Copy `dev.yaml` and `prod.yaml` and adjust
   model names, device assignments and timeouts to match your hardware.  See
   `Agents.md` for more details.

4. Start your STT and TTS services:

   * **Parakeet**:  Run the NeMo streaming server or embed Parakeet in `stt/parakeet_service.py`.
   * **VibeVoice**:  Launch the WebSocket server provided in the VibeVoice repository or run
     the containerised service.

5. Run the voice agent:

   ```bash
   python apps/server.py --profile prod  # for production with GPU
   python apps/server.py --profile dev   # for CPU‑only development
   ```

The server exposes a WebSocket endpoint that your client (browser or mobile app) can
connect to for real‑time audio streaming.  See `ui/websocket_transport.py` for client code.

## Repository structure

```
Local-Call/
├── apps/               # Entry points for running the agent
├── config/             # YAML profile and tool definitions
├── core/               # Pipeline, session management, cancellation logic
├── stt/                # Parakeet service wrapper and adapter
├── tts/                # VibeVoice service wrapper and adapter
├── llm/                # Ollama client, model router, prompt builder
├── agent/              # Reasoning loop, memory store, persona manager
├── tools/              # Custom tool implementations (search, notes, etc.)
├── ui/                 # Client transports (WebSocket, WebRTC)
├── docs/               # High‑level design documents
├── requirements.txt    # Python dependencies
├── Agents.md           # Details about each agent (STT, LLM, TTS)
├── Model-Instructions.md  # Guidance for personas and prompt engineering
└── PROJECT_GOALS.md    # Project objectives and roadmap
```

## Contributing

Contributions are welcome!  Please open issues for questions or suggestions.  Pull
requests should follow the existing code style and include tests where applicable.

## Disclaimer

This project is experimental and not affiliated with NVIDIA or Microsoft.  Use
models responsibly and respect their license terms.  The agent provides no
warranty of correctness and should not be used for safety‑critical applications.