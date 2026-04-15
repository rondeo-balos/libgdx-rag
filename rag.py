"""
rag.py — LibGDX RAG CLI REPL

Interactive terminal interface for asking LibGDX questions.
Uses the same ChromaDB index as the server.

Usage:
    python rag.py
"""

import os
import sys

import chromadb
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
TOP_K = 4


def main():
    # ─── Setup models ────────────────────────────────────────────────────
    embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )

    llm = Ollama(
        model=LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
        request_timeout=300.0,
        context_window=4096,
        additional_kwargs={"num_ctx": 4096},
    )

    Settings.embed_model = embed_model
    Settings.llm = llm

    # ─── Load index ──────────────────────────────────────────────────────
    if not os.path.isdir(CHROMA_DIR):
        print(f"❌ ChromaDB not found at '{CHROMA_DIR}'.")
        print("   Run `python ingest.py` first.")
        sys.exit(1)

    db = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        collection = db.get_collection(COLLECTION_NAME)
    except ValueError:
        print(f"❌ Collection '{COLLECTION_NAME}' not found.")
        print("   Run `python ingest.py` first.")
        sys.exit(1)

    vector_store = ChromaVectorStore(chroma_collection=collection)
    index = VectorStoreIndex.from_vector_store(vector_store)
    query_engine = index.as_query_engine(similarity_top_k=TOP_K)

    chunk_count = collection.count()
    print()
    print("─────────────────────────────────────")
    print("  🎮 LibGDX RAG Assistant")
    print(f"  📦 {chunk_count} chunks loaded")
    print(f"  🤖 Model: {LLM_MODEL}")
    print("  Type 'quit' or Ctrl+C to exit")
    print("─────────────────────────────────────")
    print()

    # ─── REPL loop ───────────────────────────────────────────────────────
    while True:
        try:
            question = input("🕹️  Ask LibGDX > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Bye!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("👋 Bye!")
            break

        print("⏳ Thinking...\n")
        response = query_engine.query(question)

        print(str(response))

        # Show sources
        if response.source_nodes:
            print("\n📎 Sources:")
            seen = set()
            for node in response.source_nodes:
                source = node.metadata.get("file_name", node.metadata.get("file_path", "unknown"))
                if source not in seen:
                    seen.add(source)
                    score = f" (score: {node.score:.3f})" if node.score else ""
                    print(f"   • {source}{score}")

        print()


if __name__ == "__main__":
    main()
