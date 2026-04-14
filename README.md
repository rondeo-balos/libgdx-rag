# LibGDX RAG Assistant

Fully local RAG assistant for LibGDX — answers grounded in real docs and source code.

**Stack:** Ollama + LlamaIndex + ChromaDB + FastAPI, all Dockerized.

## Quick Start

```bash
# 1. Pull Ollama models
ollama pull nomic-embed-text
ollama pull qwen3.5:4b

# 2. Collect knowledge base
bash scripts/collect_knowledge.sh

# 3. Build, ingest, run
docker compose build
docker compose run --rm rag python ingest.py
docker compose up
```

API at `http://localhost:8000` — try `curl localhost:8000/health`

## Docs

- [VSCode Integration (Continue.dev)](docs/VSCODE_INTEGRATION.md)
