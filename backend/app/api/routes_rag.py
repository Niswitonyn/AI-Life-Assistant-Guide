from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from app.rag.retriever import retriever
from app.rag.vector_store import vector_store


router = APIRouter()


class IngestItem(BaseModel):
    text: str = Field(min_length=1)
    metadata: Optional[Dict] = None


class IngestRequest(BaseModel):
    user_id: Optional[str] = None
    items: List[IngestItem]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = 5
    user_id: Optional[str] = None


@router.post("/ingest")
def ingest_documents(request: IngestRequest):
    try:
        ids = []
        for item in request.items:
            metadata = dict(item.metadata or {})
            if request.user_id:
                metadata["user_id"] = request.user_id
            doc_id = retriever.add_text(item.text, metadata=metadata)
            ids.append(doc_id)

        return {"status": "ok", "count": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
def search_documents(request: SearchRequest):
    try:
        filters = {"user_id": request.user_id} if request.user_id else None
        results = retriever.search(query=request.query, top_k=request.top_k, filters=filters)
        return {"status": "ok", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
def clear_documents():
    try:
        vector_store.clear()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
