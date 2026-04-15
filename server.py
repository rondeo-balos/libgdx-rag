"""
server.py — LibGDX RAG-Augmented Proxy

A transparent proxy that sits between Continue.dev and Ollama.
Every request gets enriched with relevant LibGDX documentation from ChromaDB,
then forwarded to Ollama with ALL features intact (tool calling, streaming, etc.).

Architecture:
    Continue.dev  →  this server  →  Ollama
                         ↕
                      ChromaDB
                   (LibGDX knowledge)
"""

import os
import json
import time
import logging

import chromadb
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

# ─── Configuration ───────────────────────────────────────────────────────────

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "libgdx"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5:4b")
TOP_K = int(os.getenv("RAG_TOP_K", "4"))

# Timeout for Ollama requests (model inference can be slow on small GPUs)
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300.0"))

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag-proxy")

# ─── Load ChromaDB ───────────────────────────────────────────────────────────

db = chromadb.PersistentClient(path=CHROMA_DIR)

try:
    collection = db.get_collection(COLLECTION_NAME)
except ValueError:
    raise RuntimeError(
        f"Collection '{COLLECTION_NAME}' not found in {CHROMA_DIR}. "
        "Run `python ingest.py` first."
    )

chunk_count = collection.count()
logger.info(f"✅ Loaded collection '{COLLECTION_NAME}' with {chunk_count} chunks")
logger.info(f"🤖 LLM: {LLM_MODEL} via {OLLAMA_BASE_URL}")
logger.info(f"🔍 RAG: top_k={TOP_K}, embed_model={EMBED_MODEL}")

# ─── FastAPI App ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="LibGDX RAG Proxy",
    description=(
        "RAG-augmented proxy for Ollama. Injects LibGDX knowledge into every "
        "request while preserving full OpenAI API compatibility (tool calling, "
        "streaming, etc.)."
    ),
    version="0.2.0",
)


# ─── RAG Retrieval ───────────────────────────────────────────────────────────

async def get_embedding(text: str) -> list[float]:
    """Get embedding vector from Ollama's OpenAI-compatible embeddings API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/v1/embeddings",
            json={"model": EMBED_MODEL, "input": text},
        )
        if response.status_code != 200:
            body = response.text[:500]
            raise RuntimeError(f"Ollama embed returned {response.status_code}: {body}")
        data = response.json()
        return data["data"][0]["embedding"]


async def retrieve_context(query: str, top_k: int = TOP_K) -> str:
    """Embed the query and search ChromaDB for relevant LibGDX documentation."""
    # Truncate long queries — Continue can send 30K+ chars with workspace context.
    # First ~2000 chars is more than enough to capture intent for RAG search.
    MAX_EMBED_CHARS = 2000
    embed_query = query[:MAX_EMBED_CHARS] if len(query) > MAX_EMBED_CHARS else query

    try:
        query_embedding = await get_embedding(embed_query)
    except Exception as e:
        logger.warning(f"Failed to embed query ({len(embed_query)} chars, truncated from {len(query)}): {e}")
        return ""

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    if not results["documents"] or not results["documents"][0]:
        return ""

    chunks = []
    for i, doc in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
        source = metadata.get("file_name", metadata.get("file_path", "unknown"))
        chunks.append(f"[Source: {source}]\n{doc}")

    return "\n\n---\n\n".join(chunks)


def extract_user_query(messages: list[dict]) -> str:
    """Extract the last user message from the conversation for RAG retrieval."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        # Handle multi-part content (text + images, etc.)
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            return " ".join(text_parts)
    return ""


def inject_rag_context(messages: list[dict], context: str) -> list[dict]:
    """Inject RAG context as a system message into the conversation."""
    rag_message = {
        "role": "system",
        "content": (
            "You have access to the following LibGDX documentation excerpts. "
            "Use them to inform your responses when relevant. Do not mention "
            "that you were given these excerpts unless the user asks.\n\n"
            f"--- LibGDX Documentation ---\n\n{context}\n\n--- End Documentation ---"
        ),
    }

    messages = list(messages)  # don't mutate the original

    # Insert after existing system message(s), or at the beginning
    insert_idx = 0
    for i, msg in enumerate(messages):
        if msg.get("role") == "system":
            insert_idx = i + 1
        else:
            break

    messages.insert(insert_idx, rag_message)
    return messages


# ─── Health & Models ─────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "rag-proxy",
        "collection": COLLECTION_NAME,
        "chunks": collection.count(),
        "llm": LLM_MODEL,
        "top_k": TOP_K,
    }


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


# ─── Original /chat endpoint (backward compat) ──────────────────────────────

class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Simple chat endpoint (backward compatible with the original API)."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    # Retrieve RAG context
    context = await retrieve_context(request.prompt)

    # Build messages
    messages = []
    if context:
        messages.append({
            "role": "system",
            "content": (
                "You are a LibGDX assistant. Use the following documentation "
                "to answer the question.\n\n"
                f"--- LibGDX Documentation ---\n\n{context}\n\n--- End Documentation ---"
            ),
        })
    messages.append({"role": "user", "content": request.prompt})

    # Call Ollama directly
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/v1/chat/completions",
            json={"model": LLM_MODEL, "messages": messages, "stream": False},
        )
        response.raise_for_status()
        data = response.json()

    answer = data["choices"][0]["message"]["content"]

    # Extract sources from RAG context
    sources = []
    if context:
        for line in context.split("\n"):
            if line.startswith("[Source: ") and line.endswith("]"):
                source = line[9:-1]
                if source not in sources:
                    sources.append(source)

    return ChatResponse(answer=answer, sources=sources)


# ─── OpenAI-compatible proxy (the main endpoint) ────────────────────────────

@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request):
    """
    RAG-augmented proxy to Ollama's chat completions.

    This endpoint:
    1. Extracts the last user message for RAG retrieval
    2. Searches ChromaDB for relevant LibGDX documentation
    3. Injects the docs as a system message
    4. Forwards the ENTIRE request to Ollama (tools, stream, etc.)
    5. Returns Ollama's response verbatim (including tool_calls)
    """
    body = await request.json()
    messages = body.get("messages", [])
    is_streaming = body.get("stream", False)

    # ─── Debug: log what Continue sends ──────────────────────────────
    tools = body.get("tools", [])
    logger.info(f"🔧 Request: stream={is_streaming}, tools={len(tools)}, messages={len(messages)}")
    if tools:
        tool_names = [t.get("function", {}).get("name", "?") for t in tools]
        logger.info(f"🔧 Tools sent by client: {tool_names}")
    else:
        logger.info("⚠️  No tools in request — client did not send any tool definitions")

    # ─── Filter tools for small models ───────────────────────────────
    # A 4B model can't reliably handle 13+ tools. Keep only the essentials.
    ESSENTIAL_TOOLS = {
        "read_file",
        "edit_existing_file",
        "create_new_file",
        "ls",
        "grep_search",
        "run_terminal_command",
    }
    if tools:
        filtered = [t for t in tools if t.get("function", {}).get("name") in ESSENTIAL_TOOLS]
        if len(filtered) < len(tools):
            logger.info(f"🔧 Filtered tools: {len(tools)} → {len(filtered)} (keeping essentials for small model)")
        body["tools"] = filtered
        tools = filtered

    # Log the roles in the conversation
    roles = [m.get("role", "?") for m in messages]
    logger.info(f"💬 Message roles: {roles}")

    # ─── RAG enrichment ──────────────────────────────────────────────
    user_query = extract_user_query(messages)
    if user_query.strip():
        context = await retrieve_context(user_query)
        if context:
            logger.info(
                f"📚 RAG: injecting context for query: "
                f"{user_query[:80]}{'...' if len(user_query) > 80 else ''}"
            )
            body["messages"] = inject_rag_context(messages, context)
        else:
            logger.info("📭 RAG: no relevant context found")
    else:
        logger.info("📭 RAG: no user message to retrieve for")

    # ─── Resolve model name ──────────────────────────────────────────
    # Continue sends "libgdx-rag" as the model name — map it to the real model
    model = body.get("model", LLM_MODEL)
    if model == "libgdx-rag":
        body["model"] = LLM_MODEL
    elif not model:
        body["model"] = LLM_MODEL

    # ─── Forward to Ollama ───────────────────────────────────────────
    ollama_url = f"{OLLAMA_BASE_URL}/v1/chat/completions"
    has_tools = bool(body.get("tools"))

    # IMPORTANT: Ollama doesn't return tool_calls properly in streaming mode.
    # When tools are present, we force non-streaming to Ollama so tool_calls
    # work, then convert the response back to SSE for the client.
    if has_tools:
        logger.info("🔧 Tools present — forcing non-streaming to Ollama for tool_call support")
        body["stream"] = False
        return await _proxy_with_tools(ollama_url, body, client_wants_stream=is_streaming)
    elif is_streaming:
        return await _proxy_streaming(ollama_url, body)
    else:
        return await _proxy_non_streaming(ollama_url, body)


async def _proxy_with_tools(url: str, body: dict, client_wants_stream: bool):
    """
    Forward a request with tools to Ollama (always non-streaming),
    then return the response in whatever format the client expects.
    """
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        try:
            response = await client.post(url, json=body)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Ollama request timed out. The model may still be loading.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Ollama error: {e.response.text}",
            )

    data = response.json()

    # Log whether tool_calls were returned
    choices = data.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        tool_calls = msg.get("tool_calls", [])
        content_preview = (msg.get("content", "") or "")[:80]
        if tool_calls:
            names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
            logger.info(f"✅ Ollama returned tool_calls: {names}")
        else:
            logger.info(f"💬 Ollama returned text (no tool_calls): {content_preview}...")

    # If the client wanted streaming, convert the response to SSE format
    if client_wants_stream:
        return _json_to_sse(data)
    else:
        return JSONResponse(content=data, status_code=response.status_code)


def _json_to_sse(completion: dict) -> StreamingResponse:
    """Convert a complete chat completion response into SSE chunks for streaming clients."""
    message = completion.get("choices", [{}])[0].get("message", {})
    completion_id = completion.get("id", "chatcmpl-unknown")
    created = completion.get("created", 0)
    model = completion.get("model", "unknown")

    def generate():
        # Send the full message as a single SSE chunk
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": None,
                }
            ],
        }

        # Build the delta with whatever the message contains
        delta = {"role": "assistant"}
        if message.get("content"):
            delta["content"] = message["content"]
        if message.get("tool_calls"):
            delta["tool_calls"] = message["tool_calls"]
        if message.get("reasoning"):
            delta["reasoning"] = message["reasoning"]

        chunk["choices"][0]["delta"] = delta
        chunk["choices"][0]["finish_reason"] = completion.get("choices", [{}])[0].get("finish_reason")

        yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _proxy_non_streaming(url: str, body: dict) -> JSONResponse:
    """Forward a non-streaming request to Ollama and return the response."""
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        try:
            response = await client.post(url, json=body)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Ollama request timed out. The model may still be loading.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Ollama error: {e.response.text}",
            )

    return JSONResponse(content=response.json(), status_code=response.status_code)


async def _proxy_streaming(url: str, body: dict) -> StreamingResponse:
    """Forward a streaming request to Ollama and pipe SSE chunks through."""

    async def stream_generator():
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            try:
                async with client.stream("POST", url, json=body) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.TimeoutException:
                error = {
                    "error": {
                        "message": "Ollama request timed out",
                        "type": "timeout_error",
                    }
                }
                yield f"data: {json.dumps(error)}\n\n"
            except httpx.HTTPStatusError as e:
                error = {
                    "error": {
                        "message": f"Ollama error: {e.response.text}",
                        "type": "upstream_error",
                    }
                }
                yield f"data: {json.dumps(error)}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
