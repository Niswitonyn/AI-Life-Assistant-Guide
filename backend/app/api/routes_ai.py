from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.ai.provider_factory import provider_factory
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database.db import get_db
from app.automation.task_agent import TaskAgent
from app.memory.memory_service import MemoryService
from app.memory.personalization import PersonalizationEngine
from app.rag.retriever import retriever



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


def _build_profile_prompt(profile: Dict[str, str]) -> Optional[Dict[str, str]]:
    if not profile:
        return None

    lines = [f"{key}: {value}" for key, value in profile.items()]
    return {
        "role": "system",
        "content": (
            "Known user profile facts (use for personalization when relevant):\n"
            + "\n".join(lines)
        )
    }


def _build_rag_prompt(hits: List[Dict]) -> Optional[Dict[str, str]]:
    if not hits:
        return None

    context_lines = []
    for idx, hit in enumerate(hits, start=1):
        snippet = hit.get("text", "").strip()
        if not snippet:
            continue
        context_lines.append(f"{idx}. {snippet}")

    if not context_lines:
        return None

    return {
        "role": "system",
        "content": (
            "Relevant memory context (use when helpful, ignore if irrelevant):\n"
            + "\n".join(context_lines)
        )
    }


# -------------------------
# Routes
# -------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="messages cannot be empty")

        provider = provider_factory.get_provider(
            provider_name=request.provider,
            model=request.model,
        )

        memory = MemoryService(db)
        engine = PersonalizationEngine(db)

        # -------------------------
        # 1) Get recent messages
        # -------------------------
        past_messages = memory.get_recent_messages(limit=10)

        new_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        latest_user_message = next(
            (msg.content for msg in reversed(request.messages) if msg.role == "user"),
            request.messages[-1].content
        )

        # -------------------------
        # 2) Get RAG hits
        # -------------------------
        rag_hits = retriever.search(query=latest_user_message, top_k=3)
        rag_prompt = _build_rag_prompt(rag_hits)

        # -------------------------
        # 3) Get personalization profile
        # -------------------------
        profile = engine.get_profile()
        profile_prompt = _build_profile_prompt(profile)

        # -------------------------
        # 4) Build system prompt
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

        messages = [system_prompt]
        if profile_prompt:
            messages.append(profile_prompt)
        if rag_prompt:
            messages.append(rag_prompt)
        messages += past_messages + new_messages

        # -------------------------
        # 5) Call LLM
        # -------------------------
        response = await provider.generate_response(messages)

        # -------------------------
        # 6) Save conversation
        # -------------------------
        user_text = latest_user_message
        memory.save_message("user", user_text)
        memory.save_message("assistant", response)

        # -------------------------
        # 7) Update RAG
        # -------------------------
        retriever.add_text(user_text, metadata={"role": "user", "kind": "chat"})
        retriever.add_text(response, metadata={"role": "assistant", "kind": "chat"})

        # -------------------------
        # 8) Update personalization
        # -------------------------
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
