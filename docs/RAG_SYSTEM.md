# RAG System (Personal Knowledge)

## Overview

The Personal Knowledge System lets the assistant ingest user documents (PDF/TXT/DOCX), chunk and embed them, store vectors locally, retrieve relevant chunks, and answer questions using document context.

## Ingestion Flow

1. `POST /documents/upload` (or `/api/documents/upload`)
2. File is validated (extension, size) and stored in `backend/data/documents/<user_id>/`
3. `DocumentProcessor` extracts text and splits into chunks (~700 words, with overlap)
4. Each chunk is embedded and written to the local vector store with metadata:
   - `user_id`
   - `kind=document_chunk`
   - `document_name`
   - `document_id`
   - `chunk_index`

Document metadata is persisted in SQLite table `documents`.

## Retrieval

- `Retriever.retrieve_relevant_chunks(query, top_k=5, user_id=..., document_name=...)`
  - generates a query embedding
  - performs cosine similarity search in the local vector store
  - returns top matches (default 5)

## Answering

- `BrainController._chat_fallback()` automatically adds *document* context to the prompt by searching only `kind=document_chunk`.
- For explicit commands like “summarize document X”, SmartRouter routes to `DocumentAgent`.

## Modules

- `backend/app/api/routes_documents.py`
  - upload + list endpoints
- `backend/app/rag/document_processor.py`
  - extraction + chunking + ingest
- `backend/app/rag/embeddings.py`
  - local embedding (`generate_embedding`)
- `backend/app/rag/vector_store.py`
  - JSON-backed vector storage
- `backend/app/rag/retriever.py`
  - similarity search + document chunk retrieval helper
- `backend/app/agents/document_agent.py`
  - list/summarize/ask
- `backend/app/core/rag_logs.py`
  - logs to `backend/data/logs/rag.log` and `backend/logs/rag.log`

## Security

- Extension allowlist: `.pdf`, `.txt`, `.docx`
- Size limit: `DOCUMENT_MAX_BYTES` (default 20MB)
- Upload storage is forced under `backend/data/documents/<user_id>/`

## Logs

RAG events are written as JSON lines to:

- `backend/data/logs/rag.log`
- `backend/logs/rag.log` (compat)

