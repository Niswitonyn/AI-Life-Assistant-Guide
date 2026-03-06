from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.gmail_agent import GmailAgent
from app.agents.calendar_agent import CalendarAgent


router = APIRouter()


class SendEmailRequest(BaseModel):
    user_id: str = "default"
    to: str = Field(min_length=3)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


@router.post("/gmail/send")
def gmail_send(request: SendEmailRequest):
    try:
        agent = GmailAgent(user_id=request.user_id)
        result = agent.send_email(
            to=request.to,
            subject=request.subject,
            body=request.body,
        )
        return {"status": "ok", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gmail/inbox")
def gmail_inbox(user_id: str = "default", limit: int = 5):
    try:
        agent = GmailAgent(user_id=user_id)
        emails = agent.get_latest_emails(max_results=max(1, min(limit, 20)))
        return {"status": "ok", "count": len(emails), "emails": emails}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar/upcoming")
def calendar_upcoming(user_id: str = "default", limit: int = 10):
    try:
        agent = CalendarAgent(user_id=user_id)
        events = agent.get_upcoming_events(max_results=max(1, min(limit, 20)))
        return {"status": "ok", "count": len(events), "events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
