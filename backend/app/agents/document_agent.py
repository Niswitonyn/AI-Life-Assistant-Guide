from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.core.rag_logs import log_rag_event
from app.database.models import Document
from app.rag.retriever import retriever
from app.rag.vector_store import vector_store


class DocumentAgent(BaseAgent):
    name = "document_agent"
    description = "Personal knowledge agent for uploaded documents (list/summarize/ask)."

    def __init__(self, db: Session, *, user_id: str, provider=None):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"
        self.provider = provider

    async def execute(self, task: Dict[str, Any]):
        task = task or {}
        action = (task.get("action") or "").strip()
        params = task.get("params") or {}
        task_text = task.get("text", "")

        try:
            if action == "document_list":
                return await self._list_docs(task_text)
            if action == "document_summarize":
                name = (params.get("name") or params.get("document") or "").strip()
                return await self._summarize(task_text, name=name)
            if action == "document_question":
                question = (params.get("question") or params.get("query") or task_text or "").strip()
                name = (params.get("name") or params.get("document") or "").strip() or None
                return await self._question(task_text, question=question, name=name)

            return self._err(task_text, action, f"Unsupported action: {action}")
        except Exception as e:
            log_rag_event("document_agent.error", {"user_id": self.user_id, "action": action, "task": task_text}, error=str(e))
            return self._err(task_text, action, str(e) or "Document action failed")

    async def _list_docs(self, task_text: str):
        rows = (
            self.db.query(Document)
            .filter(Document.user_id == self.user_id)
            .order_by(Document.upload_time.desc())
            .limit(100)
            .all()
        )
        docs = [{"id": r.id, "filename": r.filename, "upload_time": r.upload_time.isoformat() if r.upload_time else None, "chunk_count": r.chunk_count} for r in rows]
        log_rag_event("document.list", {"user_id": self.user_id, "count": len(docs)})
        return {
            "status": "success",
            "agent": self.name,
            "action": "document_list",
            "task": task_text,
            "result": {"documents": docs},
            "error": None,
        }

    async def _summarize(self, task_text: str, *, name: str):
        if not name:
            return self._err(task_text, "document_summarize", "Missing document name.")

        doc_name = name
        chunks = vector_store.find_documents({"user_id": self.user_id, "kind": "document_chunk", "document_name": doc_name}, limit=60)
        if not chunks:
            return self._err(task_text, "document_summarize", f"No chunks found for document '{doc_name}'.")

        # Sort by chunk_index if present.
        chunks.sort(key=lambda d: (d.get("metadata", {}) or {}).get("chunk_index", 0))
        context = "\n\n".join((c.get("text") or "") for c in chunks[:12])
        context = context[:8000]

        if not self.provider:
            summary = (context[:1200] + ("..." if len(context) > 1200 else "")).strip()
            return {
                "status": "success",
                "agent": self.name,
                "action": "document_summarize",
                "task": task_text,
                "result": {"document": doc_name, "summary": summary, "note": "No AI provider configured; returned excerpt."},
                "error": None,
            }

        prompt = (
            "Summarize the following document excerpts clearly and concisely.\n"
            f"Document: {doc_name}\n\n"
            "EXCERPTS:\n"
            f"{context}\n\n"
            "Return a helpful summary with key points."
        )
        reply = await self.provider.generate_response([{"role": "user", "content": prompt}])
        log_rag_event("document.summarize", {"user_id": self.user_id, "document": doc_name})
        return {
            "status": "success",
            "agent": self.name,
            "action": "document_summarize",
            "task": task_text,
            "result": {"document": doc_name, "summary": (reply or "").strip()},
            "error": None,
        }

    async def _question(self, task_text: str, *, question: str, name: Optional[str]):
        q = (question or "").strip()
        if not q:
            return self._err(task_text, "document_question", "Missing question.")

        hits = retriever.retrieve_relevant_chunks(q, top_k=5, user_id=self.user_id, document_name=name)
        if not hits:
            return self._err(task_text, "document_question", "No relevant document chunks found. Upload documents first.")

        context_lines: List[str] = []
        for h in hits:
            meta = h.get("metadata", {}) or {}
            doc = meta.get("document_name", "unknown")
            idx = meta.get("chunk_index", "?")
            context_lines.append(f"[{doc} chunk {idx}] {h.get('text','')}".strip())

        context = "\n\n".join(context_lines)[:8000]

        if not self.provider:
            return {
                "status": "success",
                "agent": self.name,
                "action": "document_question",
                "task": task_text,
                "result": {
                    "question": q,
                    "answer": "I can retrieve relevant excerpts, but no AI provider is configured to synthesize an answer.",
                    "excerpts": context_lines,
                },
                "error": None,
            }

        prompt = (
            "Answer the user's question using ONLY the provided document excerpts.\n"
            "If the excerpts do not contain the answer, say you don't know.\n\n"
            f"QUESTION: {q}\n\n"
            "EXCERPTS:\n"
            f"{context}\n\n"
            "Answer:"
        )
        reply = await self.provider.generate_response([{"role": "user", "content": prompt}])
        log_rag_event("document.question", {"user_id": self.user_id, "question": q, "hits": len(hits)})
        return {
            "status": "success",
            "agent": self.name,
            "action": "document_question",
            "task": task_text,
            "result": {"question": q, "answer": (reply or "").strip(), "sources": hits},
            "error": None,
        }

    def _err(self, task_text: str, action: str, error: str):
        return {"status": "error", "agent": self.name, "action": action, "task": task_text, "result": None, "error": error}

