# VSCode Integration Guide

Connect your LibGDX RAG assistant to VSCode using the **Continue.dev** extension.
Every message automatically goes through RAG — the model just *knows* LibGDX.
Full tool calling support: file edits, inline edits, and agent mode all work.

## Prerequisites

- RAG server running (`docker compose up`) 
- Ollama running on the host with `qwen3.5:4b` pulled
- `nomic-embed-text` pulled in Ollama (for RAG retrieval)

---

## Step 1 — Install Continue

1. Open VSCode
2. Go to Extensions (`Cmd+Shift+X`)
3. Search for **Continue** and install it
4. Or install from: [marketplace.visualstudio.com/items?itemName=Continue.continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue)

---

## Step 2 — Add the LibGDX RAG Model

Open Continue's config:
- Press `Cmd+Shift+P` → **Continue: Open Config File**
- Or edit `~/.continue/config.yaml` directly

Add your RAG server as a model:

```yaml
models:
  - name: "LibGDX RAG"
    provider: openai
    model: libgdx-rag
    apiBase: "http://YOUR_VPS_IP:11111/v1"
    apiKey: "not-needed"
    capabilities:
      - tool_use
```

> Replace `YOUR_VPS_IP` with your actual server IP (e.g., `192.168.1.48`).
> The `apiKey` is required by Continue but our server ignores it.
> The `capabilities: [tool_use]` tells Continue this model supports tool calling.

That's it. **No `@http`, no context providers, no extra steps.**

---

## How It Works

```
You type a message in Continue
        ↓
Continue sends full request to your RAG server
(messages + tools + stream — the whole OpenAI payload)
        ↓
Server extracts your last message
        ↓
Searches ChromaDB for relevant LibGDX docs
        ↓
Injects docs as a system message
        ↓
Forwards EVERYTHING to Ollama (tools, stream, etc.)
        ↓
Ollama responds (text, tool_calls, whatever)
        ↓
Server pipes the response back to Continue verbatim
```

You just chat normally. The RAG happens behind the scenes.
Tool calling, file edits, and agent mode all pass through transparently.

---

## Usage Modes

### Chat Mode
Ask LibGDX questions in the Continue chat panel:

- *"How do I use SpriteBatch with a camera?"*
- *"What's the best way to structure screens in LibGDX?"*
- *"Why is my Android build crashing with a GL error?"*
- *"Show me how to implement ECS with Ashley"*

### Edit Mode (`Cmd+I`)
Highlight code in your editor and ask for changes:

- *"Refactor this to use a Scene2D stage"*
- *"What's wrong with my input handling?"*
- *"Add touch controls using LibGDX best practices"*

### Agent Mode
Give multi-step tasks and the model will read/edit files:

- *"Create a new Screen class with proper lifecycle methods"*
- *"Add a particle effect system following LibGDX patterns"*
- *"Fix the rendering order in my game loop"*

> **Note:** Agent mode quality depends on the model size. A 4B model handles simple edits well but may struggle with complex multi-file refactors.

---

## Optional: Add Plain Ollama Too

You can have both the RAG model and a regular Ollama model side by side:

```yaml
models:
  - name: "LibGDX RAG"
    provider: openai
    model: libgdx-rag
    apiBase: "http://YOUR_VPS_IP:11111/v1"
    apiKey: "not-needed"
    capabilities:
      - tool_use

  - name: "Qwen (No RAG)"
    provider: ollama
    model: qwen3.5:4b
    apiBase: "http://YOUR_VPS_IP:11434"
```

Switch between them in Continue's model dropdown — use RAG for LibGDX questions, plain Qwen for everything else.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Model not found" in Continue | Check `apiBase` URL is correct and server is running |
| Slow responses | Normal for 4B model — first response takes 5-10s |
| Connection refused | Make sure `docker compose up` is running on the VPS |
| Empty answers | Re-ingest: `docker compose run --rm rag python ingest.py --reset` |
| Tool calling not working | Make sure `capabilities: [tool_use]` is in your Continue config |
| Agent mode unavailable | Update Continue to latest version; ensure tool_use capability is set |
| Want to test without VSCode | `curl http://YOUR_VPS_IP:11111/health` |
