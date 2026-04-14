"""
ingest.py — LibGDX Knowledge Base Ingestion Pipeline

Reads all documents from knowledge/, chunks them, generates embeddings
via nomic-embed-text (Ollama), and stores vectors in a persistent ChromaDB.

Usage:
    python ingest.py                     # Full ingestion
    python ingest.py --reset             # Wipe and re-ingest
"""

import os
import sys
import argparse

import chromadb
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import StorageContext
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

# ─── Configuration ───────────────────────────────────────────────────────────

KNOWLEDGE_DIR = "knowledge"
CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "libgdx"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50

# File types to ingest
SUPPORTED_EXTENSIONS = [
    ".md", ".txt", ".rst",       # docs
    ".java", ".kt", ".groovy",   # JVM source
    ".json", ".xml", ".gradle",  # config
    ".py",                       # scripts
]


def main():
    parser = argparse.ArgumentParser(description="Ingest LibGDX knowledge base")
    parser.add_argument("--reset", action="store_true", help="Wipe existing collection before ingesting")
    args = parser.parse_args()

    # ─── Validate knowledge directory ────────────────────────────────────
    if not os.path.isdir(KNOWLEDGE_DIR):
        print(f"❌ Knowledge directory '{KNOWLEDGE_DIR}' not found.")
        print("   Run: bash scripts/collect_knowledge.sh")
        sys.exit(1)

    file_count = sum(1 for _, _, files in os.walk(KNOWLEDGE_DIR) for _ in files)
    if file_count == 0:
        print(f"❌ Knowledge directory '{KNOWLEDGE_DIR}' is empty.")
        sys.exit(1)

    print(f"📂 Knowledge directory: {KNOWLEDGE_DIR} ({file_count} files)")

    # ─── Setup embedding model ───────────────────────────────────────────
    print(f"🧠 Embedding model: {EMBED_MODEL} via {OLLAMA_BASE_URL}")
    embed_model = OllamaEmbedding(
        model_name=EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )
    Settings.embed_model = embed_model

    # ─── Setup chunker ───────────────────────────────────────────────────
    splitter = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    # ─── Load documents ──────────────────────────────────────────────────
    print("📖 Loading documents...")
    reader = SimpleDirectoryReader(
        input_dir=KNOWLEDGE_DIR,
        recursive=True,
        required_exts=SUPPORTED_EXTENSIONS,
    )
    docs = reader.load_data()
    print(f"   Loaded {len(docs)} documents")

    # ─── Setup ChromaDB (persistent) ─────────────────────────────────────
    print(f"🗄️  ChromaDB path: {CHROMA_DIR}")
    db = chromadb.PersistentClient(path=CHROMA_DIR)

    if args.reset:
        print("   🔄 Resetting collection...")
        try:
            db.delete_collection(COLLECTION_NAME)
        except ValueError:
            pass  # Collection didn't exist

    collection = db.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # ─── Build index ─────────────────────────────────────────────────────
    print("⚡ Chunking and embedding (this may take a while)...")
    index = VectorStoreIndex.from_documents(
        docs,
        storage_context=storage_context,
        transformations=[splitter],
        show_progress=True,
    )

    # ─── Report ──────────────────────────────────────────────────────────
    count = collection.count()
    print()
    print("─────────────────────────────────────")
    print(f"✅ Ingestion complete!")
    print(f"   Documents loaded:  {len(docs)}")
    print(f"   Chunks stored:     {count}")
    print(f"   Collection:        {COLLECTION_NAME}")
    print(f"   Chunk size:        {CHUNK_SIZE} tokens")
    print(f"   Chunk overlap:     {CHUNK_OVERLAP} tokens")
    print("─────────────────────────────────────")


if __name__ == "__main__":
    main()
