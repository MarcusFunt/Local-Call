# Model Instructions and Persona Guidelines

The behaviour of the Local‑Call agent is largely determined by the
instructions given to the language model.  This document explains how
system prompts, tool definitions and memory work together to produce
a pleasant and safe conversational experience.  Feel free to customise
these instructions to suit your application.

## System prompt

The system prompt sets the overall behaviour and tone of the assistant.  It
is prepended to the conversation history on every turn.  A good system
prompt should:

* Describe the assistant’s role and capabilities (e.g. “You are a concise,
  friendly voice assistant.  You can search the web, call functions and
  remember user preferences.”).
* Explain tool usage rules: when uncertain, call the appropriate tool; do
  not hallucinate facts; always include citations when quoting web pages.
* Specify tone and style: use short sentences, avoid jargon, speak in a
  warm manner, ask clarification questions when necessary.
* Define any safety or privacy constraints: avoid harmful content,
  respect user confidentiality, etc.

A minimal example stored in `config/persona_default.md` might look like:

```
You are a friendly, helpful voice assistant called LocalCall.  You speak in
short, clear sentences and strive to be concise.  When you look up
information, you cite your sources (e.g. “according to the article …”).  You
can call tools when needed, such as `web_search` or `fetch_url`.

Personality guidelines:
- Be polite and approachable.
- Always ask the user for clarification if their request is ambiguous.
- Admit when you don’t know something and offer to search for it.
- Do not fabricate information.
```

## Tool definitions

Tools are defined by JSON schemas that specify their names, arguments and
descriptions.  The LLM sees these schemas and can choose to call them
when appropriate.  For example, a simple web search tool might be
registered as:

```python
tool = Tool(
    name="web_search",
    description="Search the web for up‑to‑date information.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "recency_days": {"type": "integer", "description": "Limit results to the last N days"},
            "max_results": {"type": "integer", "description": "Maximum number of results"}
        },
        "required": ["query"]
    },
    function=web_search_handler,
)
```

When the LLM produces a tool call, Pipecat will execute `web_search_handler`
with the provided arguments and supply the return value back to the model.

### Best practices for tool usage

* **Expose only necessary arguments**.  The more complex the schema, the harder
  it is for the model to call the tool correctly.
* **Return plain text** (no markdown or HTML) so that it can be spoken aloud.
* **Use short timeouts**.  A web search should return promptly or time out
  gracefully, telling the user it couldn’t retrieve results.
* **Limit side effects**.  Tools that make external changes (e.g. sending
  emails or purchasing items) should require explicit user confirmation.

## Memory and context

The agent maintains a conversation history of recent user and assistant
messages.  In addition, a **memory store** persists facts about the user
across sessions.  The `remember(key, value)` tool writes a key–value pair
into the database, while `forget(key)` deletes it.  The LLM can then
retrieve these facts through its context and incorporate them into its
responses.  When summarising or citing user information, always respect
privacy and avoid revealing sensitive data to third parties.

## Persona editing

To change the assistant’s personality, edit the Markdown file in
`config/persona_default.md` or create additional persona files.  You can
expose a tool (e.g. `set_persona(name)`) that replaces the current system
prompt.  Encourage users to define personas that match their desired tone
and level of formality.

## Prompt injection and safety

Large language models are susceptible to prompt injection attacks.  To
mitigate this:

* Treat all user input as untrusted.  Do not let the user rewrite the
  system prompt or tool definitions.
* Require confirmation before executing dangerous actions (e.g. purchases,
  account management).
* Implement a content filter that screens tool outputs for inappropriate
  content.

Following these guidelines will help you build a reliable and engaging
voice assistant.