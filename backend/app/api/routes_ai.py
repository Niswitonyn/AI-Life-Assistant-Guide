from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime
from urllib.parse import quote_plus
import re
from app.ai.provider_factory import provider_factory
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database.db import get_db
from app.automation.task_agent import TaskAgent
from app.automation.system_agent import SystemAgent
from app.memory.memory_service import MemoryService
from app.memory.personalization import PersonalizationEngine
from app.rag.retriever import retriever
from app.agents.gmail_agent import GmailAgent
from app.agents.calendar_agent import CalendarAgent
from app.agents.chrome_agent import ChromeAgent
from app.agents.file_agent import FileAgent
from app.core.auth import get_optional_current_user
from app.database.models import User



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


def _handle_time_command(user_text: str) -> Optional[str]:
    lower = (user_text or "").strip().lower()
    if not lower:
        return None

    time_keywords = [
        "time",
        "what time",
        "current time",
        "time now",
        "date",
        "today date",
        "what date",
        "day today",
    ]
    if not any(k in lower for k in time_keywords):
        return None

    now = datetime.now().astimezone()
    time_part = now.strftime("%I:%M %p").lstrip("0")
    date_part = now.strftime("%A, %d %B %Y")
    tz_part = now.tzname() or "local timezone"
    return f"It is {time_part} on {date_part} ({tz_part})."


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


def _extract_after(text: str, marker: str) -> str:
    lower = text.lower()
    idx = lower.find(marker)
    if idx < 0:
        return ""
    return text[idx + len(marker):].strip()


def _clean_command_value(value: str) -> str:
    cleaned = (value or "").strip(" ,;.")
    cleaned = re.sub(r"\s+(and|then)\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,;.")


def _split_command_candidates(text: str) -> List[str]:
    lower = text.lower()
    markers = [
        "send email to",
        "read my inbox",
        "check my inbox",
        "summarize inbox",
        "upcoming events",
        "calendar",
        "schedule",
        "open chrome and download images of",
        "open chrome and search images of",
        "open chrome and search",
        "open my documents",
        "open my downloads",
        "open my desktop",
        "open my pictures",
        "find file",
        "search file",
        "create folder called",
        "shutdown",
        "restart",
        "lock",
        "volume up",
        "volume down",
        "increase volume",
        "decrease volume",
        "mute",
        "unmute",
        "remind me to",
        "add task",
        "create task",
        "open ",
    ]

    positions: List[int] = []
    for marker in markers:
        start = 0
        while True:
            idx = lower.find(marker, start)
            if idx < 0:
                break
            positions.append(idx)
            start = idx + 1

    if not positions:
        return [text]

    positions = sorted(set(positions))
    chunks: List[str] = []
    for i, pos in enumerate(positions):
        next_pos = positions[i + 1] if i + 1 < len(positions) else len(text)
        piece = text[pos:next_pos].strip(" ,;.")
        piece = re.sub(r"^(and|then)\s+", "", piece, flags=re.IGNORECASE).strip()
        if piece:
            chunks.append(piece)

    return chunks or [text]


def _parse_single_command_clause(clause: str) -> Optional[Dict[str, Any]]:
    text = (clause or "").strip()
    lower = text.lower()
    if not lower:
        return None

    send_email = _parse_send_email_command(text)
    if send_email:
        return {"action": "gmail_send", "params": send_email}

    if any(key in lower for key in ["read my inbox", "check my inbox", "summarize inbox"]):
        return {"action": "gmail_inbox", "params": {"limit": 5}}

    if any(key in lower for key in ["calendar", "schedule", "upcoming events"]):
        return {"action": "calendar_upcoming", "params": {"limit": 5}}

    if "download images of" in lower or "search images of" in lower:
        marker = "download images of" if "download images of" in lower else "search images of"
        topic = _clean_command_value(_extract_after(text, marker))
        if topic:
            return {"action": "browser_images", "params": {"topic": topic}}

    if lower.startswith("open chrome and search"):
        query = _clean_command_value(_extract_after(text, "open chrome and search"))
        if query:
            return {"action": "browser_search", "params": {"query": query}}

    if lower.startswith("open chrome"):
        return {"action": "open_app", "params": {"app": "chrome"}}

    if "find file" in lower or "search file" in lower:
        marker = "find file" if "find file" in lower else "search file"
        name = _clean_command_value(_extract_after(text, marker))
        if name:
            return {"action": "file_find", "params": {"name": name}}

    if "create folder called" in lower:
        folder_name = _clean_command_value(_extract_after(text, "create folder called"))
        if folder_name:
            return {"action": "folder_create", "params": {"name": folder_name, "base": "documents"}}

    if "open my documents" in lower:
        return {"action": "folder_open", "params": {"target": "documents"}}
    if "open my downloads" in lower:
        return {"action": "folder_open", "params": {"target": "downloads"}}
    if "open my desktop" in lower:
        return {"action": "folder_open", "params": {"target": "desktop"}}
    if "open my pictures" in lower:
        return {"action": "folder_open", "params": {"target": "pictures"}}

    if lower.startswith("open "):
        app_name = _clean_command_value(_extract_after(text, "open"))
        if app_name and app_name not in {"my documents", "my downloads", "my desktop", "my pictures"}:
            return {"action": "open_app", "params": {"app": app_name}}

    if any(k in lower for k in [
        "shutdown", "restart", "lock",
        "volume up", "volume down", "mute", "unmute",
        "increase volume", "decrease volume"
    ]):
        return {"action": "system_execute", "params": {"command": text}}

    if "remind me to" in lower or lower.startswith("add task") or lower.startswith("create task"):
        return {"action": "task_create", "params": {"text": text}}

    return None


def _parse_command_schema(user_text: str) -> Optional[Dict[str, Any]]:
    text = (user_text or "").strip()
    if not text:
        return None

    # Keep email parsing as a single clause to avoid splitting email body text.
    send_email = _parse_send_email_command(text)
    if send_email:
        return {"schema": "phase3.command.v1", "commands": [{"action": "gmail_send", "params": send_email}]}

    actions: List[Dict[str, Any]] = []
    for clause in _split_command_candidates(text):
        parsed = _parse_single_command_clause(clause)
        if parsed:
            actions.append(parsed)

    # Final fallback for single-clause command text.
    if not actions:
        parsed = _parse_single_command_clause(text)
        if parsed:
            actions.append(parsed)

    if not actions:
        return None

    return {"schema": "phase3.command.v1", "commands": actions}


def _execute_single_action(action: str, params: Dict[str, Any], user_id: str, db: Session) -> Optional[str]:
    try:
        if action == "gmail_send":
            agent = GmailAgent(user_id=user_id)
            result = agent.send_email(
                to=params.get("to", ""),
                subject=params.get("subject", "Message from Jarvis"),
                body=params.get("body", ""),
            )
            return f"{result}. To: {params.get('to')}. Subject: {params.get('subject')}."

        if action == "gmail_inbox":
            agent = GmailAgent(user_id=user_id)
            emails = agent.get_latest_emails(max_results=int(params.get("limit", 5)))
            if not emails:
                return "No emails found in inbox."
            lines = [f"{i + 1}. {snippet}" for i, snippet in enumerate(emails)]
            return "Here are your latest inbox items:\n" + "\n".join(lines)

        if action == "calendar_upcoming":
            agent = CalendarAgent(user_id=user_id)
            events = agent.get_upcoming_events(max_results=int(params.get("limit", 5)))
            if not events:
                return "No upcoming calendar events found."
            lines = [f"{i + 1}. {event['summary']} at {event['start']}" for i, event in enumerate(events)]
            return "Here are your upcoming events:\n" + "\n".join(lines)

        if action == "browser_search":
            query = params.get("query", "").strip()
            ChromeAgent().open(query=quote_plus(query), browser="chrome")
            return f"Opened Chrome search for: {params.get('query', '')}"

        if action == "browser_images":
            topic = params.get("topic", "").strip()
            ChromeAgent().open(query=f"{quote_plus(topic)}&tbm=isch", browser="chrome")
            return f"Opened Chrome image results for: {topic}"

        if action == "open_app":
            result = SystemAgent().execute(f"open {params.get('app', '')}")
            return result or f"Could not open {params.get('app', 'app')}"

        if action == "file_find":
            found = FileAgent().find_file(params.get("name", ""))
            return f"Found file: {found}" if found else f"No file found for: {params.get('name', '')}"

        if action == "folder_create":
            path = FileAgent().create_folder(params.get("name", ""), base=params.get("base", "documents"))
            return f"Created folder: {path}" if path else "Could not create folder"

        if action == "folder_open":
            result = SystemAgent().execute(f"open {params.get('target', '')}")
            return result or f"Could not open {params.get('target', '')}"

        if action == "system_execute":
            result = SystemAgent().execute(params.get("command", ""))
            return result or "Could not execute system command"

        if action == "task_create":
            task = TaskAgent(db).create_task_from_text(params.get("text", ""))
            return f"Task created: {task.title}"
    except Exception:
        if action in {"gmail_send", "gmail_inbox", "calendar_upcoming"}:
            return (
                "I could not access Gmail/Calendar. "
                "Please connect Google in Settings and ensure required scopes are enabled."
            )
        return f"Action failed: {action}"

    return None


def _execute_command_schema(command_schema: Dict[str, Any], user_id: str, db: Session) -> Optional[str]:
    commands = command_schema.get("commands", [])
    if not commands:
        return None

    replies: List[str] = []
    for command in commands:
        action = command.get("action")
        params = command.get("params", {})
        reply = _execute_single_action(action, params, user_id, db)
        if reply:
            replies.append(reply)

    if not replies:
        return None
    if len(replies) == 1:
        return replies[0]
    return "\n".join([f"{idx + 1}. {reply}" for idx, reply in enumerate(replies)])


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

        time_reply = _handle_time_command(latest_user_message)
        if time_reply:
            memory.save_message(request_user_id, "user", latest_user_message)
            memory.save_message(request_user_id, "assistant", time_reply)
            retriever.add_text(
                latest_user_message,
                metadata={"user_id": request_user_id, "role": "user", "kind": "chat"}
            )
            retriever.add_text(
                time_reply,
                metadata={"user_id": request_user_id, "role": "assistant", "kind": "chat"}
            )
            return ChatResponse(response=time_reply)

        command = _parse_command_schema(latest_user_message)
        if command:
            command_reply = _execute_command_schema(command, request_user_id, db)
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
