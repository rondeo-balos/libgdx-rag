What RAG actually is (super simple)

Your model does NOT memorize LibGDX.

Instead, it does this every question:
	1.	Search your LibGDX knowledge base
	2.	Grab relevant docs/code
	3.	Give them to the model as context
	4.	Model answers using that context

So the model becomes a reader, not a guesser.

This is why hallucination drops massively.

⸻

Your current setup

You already have:
	•	Ollama ✔
	•	qwen3.5:4B ✔ (great choice for local RAG)

You only need the RAG pipeline.

⸻

The 4 things you need for RAG

1️⃣ Documents (your knowledge base)

This is the most important part.

Create a folder like:

knowledge/
   libgdx-wiki/
   libgdx-javadoc/
   libgdx-examples/
   libgdx-github-issues/
   stackoverflow-libgdx/
   my-own-projects/

Put inside:
	•	markdown
	•	pdf
	•	txt
	•	java files
	•	blog posts

The bigger and cleaner this is → the smarter your assistant.

Think of this as the model’s “memory”.

⸻

2️⃣ Embedding model (the search brain)

The model can’t search text directly.
We convert text → vectors.

With Ollama you can simply pull one:

ollama pull nomic-embed-text

This model turns every chunk of text into numbers so we can search semantically.

Example:

“How to use SpriteBatch?”
Finds docs even if the words differ.

⸻

3️⃣ Vector database (the memory storage)

This stores all embeddings so we can search fast.

Beginner-friendly choices:
	•	Chroma (easiest)
	•	LanceDB
	•	Weaviate

For local projects → use Chroma.

Install:

pip install chromadb


⸻

4️⃣ RAG orchestrator (the glue)

This is the code that connects:
	•	embeddings
	•	vector DB
	•	Ollama model

Two popular frameworks:
	•	LangChain
	•	LlamaIndex

For beginners → LlamaIndex is easier.

Install:

pip install llama-index llama-index-llms-ollama llama-index-embeddings-ollama


⸻

The pipeline you’re building

LibGDX docs → chunk text → embed → store in Chroma
User question → embed question → search Chroma
Top results → send to Qwen → answer

That’s RAG 🙂

⸻

Minimal working code (your first RAG)

Create rag.py:

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

# 1. Load documents
docs = SimpleDirectoryReader("knowledge").load_data()

# 2. Setup embedding model
embed_model = OllamaEmbedding(model_name="nomic-embed-text")

# 3. Setup LLM
llm = Ollama(model="qwen3.5:4b")

# 4. Build index (creates vector DB)
index = VectorStoreIndex.from_documents(
    docs,
    embed_model=embed_model
)

# 5. Create chat engine
query_engine = index.as_query_engine(llm=llm)

while True:
    q = input("Ask LibGDX AI > ")
    response = query_engine.query(q)
    print("\n", response, "\n")

Run:

python rag.py

Boom 💥
You now have a LibGDX RAG assistant.

⸻

How to make it GOOD (important)

Chunking (huge improvement)

LLMs work best with small chunks of docs.

Later you’ll tune:
	•	chunk size 300–800 tokens
	•	overlap 50 tokens

This dramatically improves accuracy.

⸻

Add GitHub repos (huge boost)

Clone repos into your knowledge folder:

git clone https://github.com/libgdx/libgdx
git clone https://github.com/libgdx/libgdx-demo-superjumper

RAG becomes insanely good with real code.

⸻

Add your own projects (secret weapon)

Your assistant will learn:
	•	your architecture
	•	your patterns
	•	your naming
	•	your mistakes 😄

This becomes a personal coding copilot.

⸻

What happens next (future upgrades)

Once this works, you can add:

Upgrade	Effect
Hybrid search (BM25 + vector)	massive accuracy boost
Re-ranking model	better doc selection
Fine-tune qwen	LibGDX expert mode
Web UI	ChatGPT-style interface

But first: get basic RAG working.

⸻

Reality check

After you ingest docs + repos, your assistant will be able to answer things like:
	•	“Why does SpriteBatch cause flickering?”
	•	“How to structure screens in LibGDX?”
	•	“Best ECS architecture?”
	•	“Why is my Android build crashing?”

And it will answer using real LibGDX docs and code.

No guessing.

⸻

You basically want:

VSCode → your local RAG → Ollama (qwen) → LibGDX knowledge

⸻

TL;DR

Best option today 👉 Use the Continue extension + your RAG API

Claude-Code is great, but it’s not designed for local RAG pipelines yet.

Let’s compare properly.

⸻

Option 1 — Continue extension (BEST)

Continue is basically “local Copilot you control”.

It already supports:
	•	Ollama
	•	local models
	•	custom context providers
	•	workspace indexing
	•	RAG APIs

This makes it PERFECT for what you’re building.

Why it fits your project:
	•	It can call your local RAG server
	•	It can read your workspace files
	•	It supports chat + inline edits
	•	Fully local, no cloud needed

This is exactly the architecture you want.

⸻

How the architecture would look

VSCode (Continue)
      ↓
Local RAG API (Python / FastAPI)
      ↓
Chroma vector DB (LibGDX knowledge)
      ↓
Ollama (qwen3.5:4B)

Continue becomes just the UI + editor integration.

Your RAG becomes the brain.

⸻

Step 1 — Install Continue

In VSCode extensions search:

Continue.dev

Open settings → open continue.config.json

⸻

Step 2 — Connect Continue to Ollama

Add:

{
  "models": [
    {
      "title": "Local Qwen",
      "provider": "ollama",
      "model": "qwen3.5:4b"
    }
  ]
}

Now Continue can already chat with your local model.

But we want the next level 👇

⸻

Step 3 — Turn your RAG into an API

Right now your RAG runs in a terminal loop.
VSCode needs an HTTP endpoint.

Install FastAPI:

pip install fastapi uvicorn

Create server.py:

from fastapi import FastAPI
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

app = FastAPI()

docs = SimpleDirectoryReader("knowledge").load_data()
embed_model = OllamaEmbedding(model_name="nomic-embed-text")
llm = Ollama(model="qwen3.5:4b")

index = VectorStoreIndex.from_documents(docs, embed_model=embed_model)
query_engine = index.as_query_engine(llm=llm)

@app.post("/chat")
async def chat(prompt: str):
    response = query_engine.query(prompt)
    return {"answer": str(response)}

Run it:

uvicorn server:app --reload --port 8000

Your RAG is now an API 🎉

⸻

Step 4 — Connect Continue to your RAG

Continue supports custom endpoints.

Add to config:

{
  "models": [
    {
      "title": "LibGDX Assistant",
      "provider": "openai",
      "apiBase": "http://localhost:8000",
      "model": "rag"
    }
  ]
}

Now VSCode thinks your RAG is an OpenAI-style model.

And boom:
	•	Ask questions about your code
	•	Ask LibGDX questions
	•	Refactor files
	•	Generate code

All using your local knowledge.