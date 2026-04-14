FROM python:3.12-slim

WORKDIR /app

# Install deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ingest.py server.py rag.py ./

# Volumes for persistent data (mounted via docker-compose)
# - /app/knowledge   → raw documents
# - /app/chroma_db   → vector store

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
