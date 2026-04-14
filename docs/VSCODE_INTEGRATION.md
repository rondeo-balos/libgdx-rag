# VSCode Integration Guide

Connect your LibGDX RAG assistant to VSCode using the **Continue.dev** extension.
Every message automatically goes through RAG — the model just *knows* LibGDX.

## Prerequisites

- RAG server running (`docker compose up`) 
- Ollama running on the host with `qwen3.5:4b` pulled

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
  - title: "LibGDX RAG"
    provider: openai
    model: libgdx-rag
    apiBase: "http://YOUR_VPS_IP:11111/v1"
    apiKey: "not-needed"
```

> Replace `YOUR_VPS_IP` with your actual server IP (e.g., `192.168.1.48`).
> The `apiKey` is required by Continue but our server ignores it.

That's it. **No `@http`, no context providers, no extra steps.**

---

## How It Works

```
You type a question in Continue
        ↓
Continue sends it to your RAG server (OpenAI-compatible API)
        ↓
Server searches ChromaDB for relevant LibGDX docs
        ↓
Sends docs + your question to Qwen via Ollama
        ↓
Answer appears in Continue — grounded in real docs
```

You just chat normally. The RAG happens behind the scenes.

---

## Usage Examples

Just ask in the Continue chat panel like you would with any AI:

- *"How do I use SpriteBatch with a camera?"*
- *"What's the best way to structure screens in LibGDX?"*
- *"Why is my Android build crashing with a GL error?"*
- *"Show me how to implement ECS with Ashley"*

Highlight code in your editor and ask:
- *"Refactor this to use a Scene2D stage"*
- *"What's wrong with my input handling?"*

---

## Optional: Add Plain Ollama Too

You can have both the RAG model and a regular Ollama model side by side:

```yaml
models:
  - title: "LibGDX RAG"
    provider: openai
    model: libgdx-rag
    apiBase: "http://YOUR_VPS_IP:11111/v1"
    apiKey: "not-needed"

  - title: "Qwen (No RAG)"
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
| Want to test without VSCode | `curl http://YOUR_VPS_IP:11111/health` |
