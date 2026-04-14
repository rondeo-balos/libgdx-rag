import os
import json
import time
import uuid

import chromadb
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.chroma import ChromaVectorStore

# ─── Configuration ───────────────────────────────────────────────────────────

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "libgdx"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5:4b")
TOP_K = 5  # Number of chunks to retrieve per query

# ─── Setup Models ────────────────────────────────────────────────────────────

embed_model = OllamaEmbedding(
    model_name=EMBED_MODEL,
    base_url=OLLAMA_BASE_URL,
)

llm = Ollama(
    model=LLM_MODEL,
    base_url=OLLAMA_BASE_URL,
    request_timeout=120.0,
)

Settings.embed_model = embed_model
Settings.llm = llm

# ─── Load Index ──────────────────────────────────────────────────────────────

db = chromadb.PersistentClient(path=CHROMA_DIR)

try:
    collection = db.get_collection(COLLECTION_NAME)
except ValueError:
    raise RuntimeError(
        f"Collection '{COLLECTION_NAME}' not found in {CHROMA_DIR}. "
        "Run `python ingest.py` first."
    )

vector_store = ChromaVectorStore(chroma_collection=collection)
index = VectorStoreIndex.from_vector_store(vector_store)
query_engine = index.as_query_engine(similarity_top_k=TOP_K)

print(f"✅ Loaded collection '{COLLECTION_NAME}' with {collection.count()} chunks")
print(f"🤖 LLM: {LLM_MODEL} via {OLLAMA_BASE_URL}")

# ─── FastAPI App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="LibGDX RAG Assistant",
    description="Ask questions about LibGDX — answers grounded in real docs and source code.",
    version="0.1.0",
)


# ─── Original endpoints ─────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "collection": COLLECTION_NAME,
        "chunks": collection.count(),
        "llm": LLM_MODEL,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    response = query_engine.query(request.prompt)

    # Extract source file paths from the response metadata
    sources = []
    if response.source_nodes:
        for node in response.source_nodes:
            meta = node.metadata
            source = meta.get("file_name", meta.get("file_path", "unknown"))
            if source not in sources:
                sources.append(source)

    return ChatResponse(
        answer=str(response),
        sources=sources,
    )


# ─── OpenAI-compatible API ──────────────────────────────────────────────────
# This makes the RAG server look like an OpenAI model to Continue.dev.
# Every message automatically goes through RAG — no @http needed.

class OAIMessage(BaseModel):
    role: str
    content: str


class OAIChatRequest(BaseModel):
    model: str = "libgdx-rag"
    messages: list[OAIMessage]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    return {
        "object": "list",
        "data": [
            {
                "id": "libgdx-rag",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def openai_chat(request: OAIChatRequest):
    """OpenAI-compatible chat completions — every message goes through RAG."""

    # Extract the last user message as the query
    user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break

    if not user_message.strip():
        raise HTTPException(status_code=400, detail="No user message found")

    # Run through RAG pipeline
    response = query_engine.query(user_message)
    answer = str(response)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    # ─── Streaming response (SSE) ────────────────────────────────────
    if request.stream:
        def generate_stream():
            # Send the full answer as a single chunk
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "libgdx-rag",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": answer},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

            # Send the stop chunk
            stop_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": "libgdx-rag",
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(stop_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
        )

    # ─── Non-streaming response ──────────────────────────────────────
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": "libgdx-rag",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": answer,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

