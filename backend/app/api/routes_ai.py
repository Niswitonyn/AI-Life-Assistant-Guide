from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.ai.provider_factory import provider_factory
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database.db import get_db
from app.automation.task_agent import TaskAgent
from app.memory.conversation import ConversationManager
from app.memory.context_store import ContextStore
from app.memory.memory_service import MemoryService
from app.memory.personalization import PersonalizationEngine



router = APIRouter()


# -------------------------
# Request Models
# -------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    response: str


# -------------------------
# Routes
# -------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    try:
        from app.memory.memory_service import MemoryService

        provider = provider_factory.get_provider(
            provider_name=request.provider,
            model=request.model,
        )

        memory = MemoryService(db)

        # -------------------------
        # Load Past Memory
        # -------------------------
        past_messages = memory.get_recent_messages(limit=10)

        new_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        # Combine memory + new
        messages = past_messages + new_messages

        # -------------------------
        # Jarvis System Prompt
        # -------------------------
        system_prompt = {
            "role": "system",
            "content": (
                "You are Jarvis, a highly intelligent personal AI assistant. "
                "You are helpful, concise, polite, and slightly witty. "
                "You remember user preferences and personalize responses. "
                "Always aim to assist efficiently."
            )
        }

        messages = [system_prompt] + messages

        # -------------------------
        # AI Response
        # -------------------------
        response = await provider.generate_response(messages)

        # -------------------------
        # Save Conversation
        # -------------------------
        user_text = request.messages[-1].content

        memory.save_message("user", user_text)
        memory.save_message("assistant", response)

        # -------------------------
        # Personalization Engine
        # -------------------------
        engine = PersonalizationEngine(db)
        engine.process_user_text(user_text)

        # -------------------------
        # Task Detection
        # -------------------------
        user_lower = user_text.lower()

        if "task" in user_lower or "remind" in user_lower:
            agent = TaskAgent(db)
            agent.create_task_from_text(user_lower)

        return ChatResponse(response=response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





@router.get("/models")
async def list_models(provider: Optional[str] = None):
    """
    List available models for selected provider.
    """

    try:
        provider_instance = provider_factory.get_provider(provider_name=provider)

        models = await provider_instance.list_models()

        return {"models": models}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def provider_health(provider: Optional[str] = None):
    """
    Check provider health.
    """

    try:
        provider_instance = provider_factory.get_provider(provider_name=provider)

        healthy = await provider_instance.health_check()

        return {"healthy": healthy}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
