from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from typing import List, Optional

from app.ai.provider_factory import provider_factory
from app.core.auth import get_optional_current_user
from app.core.brain_controller import BrainController
from app.database.db import get_db
from app.database.models import User


router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


_SUPPORTED_PROVIDERS = {"ollama", "openai", "gemini"}


class ChatRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    user_id: str = "default"
    messages: List[ChatMessage]

    @field_validator("provider", mode="before")
    @classmethod
    def _validate_provider(cls, v):
        if v is None:
            return v
        if v.lower() not in _SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider '{v}'. Must be one of: {sorted(_SUPPORTED_PROVIDERS)}")
        return v.lower()


class ChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    if not any((msg.content or "").strip() for msg in request.messages if msg.role == "user"):
        raise HTTPException(status_code=400, detail="user message cannot be empty")

    request_user_id = current_user.user_id if current_user else ((request.user_id or "").strip() or "default")
    request_user_id = (request_user_id or "").strip() or "default"

    latest_user_message = next(
        (msg.content for msg in reversed(request.messages) if msg.role == "user"),
        request.messages[-1].content,
    )
    latest_user_message = (latest_user_message or "").strip()
    if not latest_user_message:
        raise HTTPException(status_code=400, detail="user message cannot be empty")

    brain = BrainController(
        db=db,
        user_id=request_user_id,
        provider=request.provider,
        model=request.model,
        is_authenticated=bool(current_user),
    )
    result = await brain.handle_text(latest_user_message)
    if result.get("status") == "needs_confirmation":
        prompt = ((result.get("result") or {}).get("prompt") or "").strip()
        return ChatResponse(response=prompt or "Please confirm to proceed.")
    return ChatResponse(response=(result.get("response_text", "") or "").strip())


@router.get("/models")
async def list_models(provider: Optional[str] = None):
    provider_instance = provider_factory.get_provider(provider_name=provider)
    models = await provider_instance.list_models()
    return {"models": models}


@router.get("/health")
async def provider_health(provider: Optional[str] = None):
    provider_instance = provider_factory.get_provider(provider_name=provider)
    healthy = await provider_instance.health_check()
    return {"healthy": healthy}
