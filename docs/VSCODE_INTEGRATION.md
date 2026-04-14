# VSCode Integration Guide

Connect your LibGDX RAG assistant to VSCode using the **Continue.dev** extension.

## Prerequisites

- RAG server running (`docker compose up`) at `http://localhost:8000`
- Ollama running on the host with `qwen3.5:4b` pulled

---

## Step 1 — Install Continue

1. Open VSCode
2. Go to Extensions (`Cmd+Shift+X`)
3. Search for **Continue** and install it
4. Or install from: [marketplace.visualstudio.com/items?itemName=Continue.continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue)

---

## Step 2 — Configure the Chat Model (Ollama)

Open Continue's config file:
- Press `Cmd+Shift+P` → **Continue: Open Config File**
- Or edit `~/.continue/config.yaml` directly

Add your local Ollama model:

```yaml
models:
  - title: "LibGDX Assistant (Local)"
    provider: ollama
    model: qwen3.5:4b
```

This gives you a local chat model in VSCode. But we want it **grounded in LibGDX docs** — that's where the RAG context provider comes in.

---

## Step 3 — Connect the RAG Context Provider

Continue supports pulling external context via HTTP. Add this to your `config.yaml`:

```yaml
contextProviders:
  - name: http
    params:
      url: "http://localhost:8000/chat"
      title: "LibGDX Docs"
      description: "Search LibGDX documentation and source code"
```

### How to use it

In the Continue chat panel, type `@http` and then your question:

```
@http How do I use SpriteBatch with a camera?
```

Continue will call your local RAG server, grab the relevant LibGDX docs, and feed them to the model as context.

---

## Alternative: MCP Server (Advanced)

If you want richer integration (multi-step reasoning, tool calling), you can wrap the RAG as an MCP server. This is more work but gives Continue deep access to your knowledge base.

### Quick MCP setup

1. Install the MCP SDK:
   ```bash
   pip install mcp
   ```

2. Create `mcp_server.py` in the project:
   ```python
   from mcp.server.fastmcp import FastMCP
   import chromadb
   from llama_index.core import VectorStoreIndex, Settings
   from llama_index.embeddings.ollama import OllamaEmbedding
   from llama_index.llms.ollama import Ollama
   from llama_index.vector_stores.chroma import ChromaVectorStore

   mcp = FastMCP("LibGDX RAG")

   # Setup (same as server.py)
   embed_model = OllamaEmbedding(model_name="nomic-embed-text")
   llm = Ollama(model="qwen3.5:4b", request_timeout=120.0)
   Settings.embed_model = embed_model
   Settings.llm = llm

   db = chromadb.PersistentClient(path="chroma_db")
   collection = db.get_collection("libgdx")
   vector_store = ChromaVectorStore(chroma_collection=collection)
   index = VectorStoreIndex.from_vector_store(vector_store)
   query_engine = index.as_query_engine(similarity_top_k=5)

   @mcp.tool()
   def search_libgdx(question: str) -> str:
       """Search LibGDX documentation and source code for answers."""
       response = query_engine.query(question)
       return str(response)

   if __name__ == "__main__":
       mcp.run(transport="stdio")
   ```

3. Add to Continue config:
   ```yaml
   mcpServers:
     - name: "LibGDX RAG"
       command: "python"
       args: ["mcp_server.py"]
       cwd: "/path/to/libgdx-rag"
   ```

4. In Continue, the `search_libgdx` tool will be available automatically.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Continue can't reach Ollama | Make sure Ollama is running: `ollama serve` |
| `@http` returns errors | Check the RAG server is up: `curl http://localhost:8000/health` |
| Slow responses | Expected with 4B model — first response takes 5-10s |
| Model not found | Run `ollama pull qwen3.5:4b` |
| Empty/bad answers | Re-ingest with `--reset`: `docker compose run --rm rag python ingest.py --reset` |

---

## Tips

- **Use `@http` for specific questions** — "How does Scene2D handle touch events?" works better than "explain Scene2D"
- **Combine with workspace context** — highlight code in your editor, then ask Continue to explain or refactor it using `@http` for LibGDX-specific knowledge
- **Keep the knowledge base fresh** — when LibGDX updates, re-run `bash scripts/collect_knowledge.sh` then `docker compose run --rm rag python ingest.py --reset`
