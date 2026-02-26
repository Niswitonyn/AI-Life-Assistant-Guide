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
from app.agents.gmail_agent import GmailAgent
from app.agents.calendar_agent import CalendarAgent
from app.core.auth import get_optional_current_user
from app.models.user import User



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
    user_id: str = "default"
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    response: str


def _parse_send_email_command(text: str) -> Optional[Dict[str, str]]:
    lower = text.lower().strip()
    trigger = "send email to "
    if not lower.startswith(trigger):
        return None

    raw = text.strip()[len(trigger):].strip()
    if not raw:
        return None

    parts = raw.split(" subject ", 1)
    to_email = parts[0].strip()

    subject = "Message from Jarvis"
    body = "Hello,\n\nThis is a message sent by Jarvis.\n\nBest regards"

    if len(parts) > 1:
        tail = parts[1]
        if " body " in tail:
            subject_part, body_part = tail.split(" body ", 1)
            subject = subject_part.strip() or subject
            body = body_part.strip() or body
        else:
            subject = tail.strip() or subject
    elif " about " in raw:
        to_part, topic = raw.split(" about ", 1)
        to_email = to_part.strip()
        subject = f"About {topic.strip()}" if topic.strip() else subject
        body = f"Hello,\n\nI am reaching out about {topic.strip()}.\n\nBest regards"

    if not to_email:
        return None

    return {
        "to": to_email,
        "subject": subject,
        "body": body,
    }


def _handle_productivity_command(user_text: str, user_id: str) -> Optional[str]:
    text = user_text.strip()
    lower = text.lower()

    try:
        send_email = _parse_send_email_command(text)
        if send_email:
            agent = GmailAgent(user_id=user_id)
            result = agent.send_email(
                to=send_email["to"],
                subject=send_email["subject"],
                body=send_email["body"],
            )
            return f"{result}. To: {send_email['to']}. Subject: {send_email['subject']}."

        if any(key in lower for key in ["read my inbox", "check my inbox", "summarize inbox"]):
            agent = GmailAgent(user_id=user_id)
            emails = agent.get_latest_emails(max_results=5)
            if not emails:
                return "No emails found in inbox."
            lines = [f"{i + 1}. {snippet}" for i, snippet in enumerate(emails)]
            return "Here are your latest inbox items:\n" + "\n".join(lines)

        if any(key in lower for key in ["calendar", "schedule", "upcoming events"]):
            agent = CalendarAgent(user_id=user_id)
            events = agent.get_upcoming_events(max_results=5)
            if not events:
                return "No upcoming calendar events found."
            lines = [
                f"{i + 1}. {event['summary']} at {event['start']}"
                for i, event in enumerate(events)
            ]
            return "Here are your upcoming events:\n" + "\n".join(lines)
    except Exception:
        return (
            "I could not access Gmail/Calendar. "
            "Please connect Google in Settings and ensure required scopes are enabled."
        )

    return None


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
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="messages cannot be empty")
        if not any((msg.content or "").strip() for msg in request.messages if msg.role == "user"):
            raise HTTPException(status_code=400, detail="user message cannot be empty")
        request_user_id = str(current_user.id) if current_user else ((request.user_id or "default").strip() or "default")

        provider = provider_factory.get_provider(
            provider_name=request.provider,
            model=request.model,
        )

        memory = MemoryService(db)
        engine = PersonalizationEngine(db)

        # -------------------------
        # 1) Get recent messages
        # -------------------------
        past_messages = memory.get_recent_messages(user_id=request_user_id, limit=10)

        new_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        latest_user_message = next(
            (msg.content for msg in reversed(request.messages) if msg.role == "user"),
            request.messages[-1].content
        )
        latest_user_message = (latest_user_message or "").strip()
        if not latest_user_message:
            raise HTTPException(status_code=400, detail="user message cannot be empty")

        command_reply = _handle_productivity_command(latest_user_message, request_user_id)
        if command_reply:
            memory.save_message(request_user_id, "user", latest_user_message)
            memory.save_message(request_user_id, "assistant", command_reply)
            retriever.add_text(
                latest_user_message,
                metadata={"user_id": request_user_id, "role": "user", "kind": "chat"}
            )
            retriever.add_text(
                command_reply,
                metadata={"user_id": request_user_id, "role": "assistant", "kind": "chat"}
            )
            engine.process_user_text(request_user_id, latest_user_message)
            return ChatResponse(response=command_reply)

        # -------------------------
        # 2) Get RAG hits
        # -------------------------
        rag_hits = retriever.search(
            query=latest_user_message,
            top_k=3,
            filters={"user_id": request_user_id}
        )
        rag_prompt = _build_rag_prompt(rag_hits)

        # -------------------------
        # 3) Get personalization profile
        # -------------------------
        profile = engine.get_profile(request_user_id)
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
        memory.save_message(request_user_id, "user", user_text)
        memory.save_message(request_user_id, "assistant", response)

        # -------------------------
        # 7) Update RAG
        # -------------------------
        retriever.add_text(
            user_text,
            metadata={"user_id": request_user_id, "role": "user", "kind": "chat"}
        )
        retriever.add_text(
            response,
            metadata={"user_id": request_user_id, "role": "assistant", "kind": "chat"}
        )

        # -------------------------
        # 8) Update personalization
        # -------------------------
        engine.process_user_text(request_user_id, user_text)

        # -------------------------
        # Task Detection
        # -------------------------
        user_lower = user_text.lower()

        if "task" in user_lower or "remind" in user_lower:
            agent = TaskAgent(db)
            agent.create_task_from_text(user_lower)

        return ChatResponse(response=response)

    except HTTPException:
        raise
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
