from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_optional_current_user
from app.database.db import get_db
from app.database.models import User
from app.memory.conversation_memory import ConversationMemoryStore
from app.memory.long_term_memory import LongTermMemory
from app.memory.semantic_memory import SemanticMemory


router = APIRouter()


@router.get("/history")
def get_memory_history(
    user_id: str = "default",
    session_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    resolved_user_id = current_user.user_id if current_user else ((user_id or "").strip() or "default")
    store = ConversationMemoryStore(db=db, user_id=resolved_user_id)
    history = store.get_conversation_history(limit=limit, session_id=session_id)
    return {"user_id": resolved_user_id, "count": len(history), "items": history}


@router.get("/search")
def search_memory(
    query: str,
    user_id: str = "default",
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    q = (query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query cannot be empty")

    resolved_user_id = current_user.user_id if current_user else ((user_id or "").strip() or "default")
    semantic = SemanticMemory(db=db, user_id=resolved_user_id).search_related_memory(query=q, limit=limit)
    long_term = LongTermMemory(db=db, user_id=resolved_user_id).search_by_text(query=q, limit=limit)
    return {
        "user_id": resolved_user_id,
        "query": q,
        "semantic_results": semantic,
        "long_term_results": long_term,
    }


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: int,
    user_id: str = "default",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    resolved_user_id = current_user.user_id if current_user else ((user_id or "").strip() or "default")
    ok = LongTermMemory(db=db, user_id=resolved_user_id).delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"status": "deleted", "id": memory_id}
