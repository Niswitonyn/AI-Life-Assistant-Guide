from __future__ import annotations

import json
from typing import Dict, Optional

from app.ai.base_provider import BaseAIProvider


class EmailAIService:
    def __init__(self, provider: BaseAIProvider):
        self.provider = provider

    async def improve_email(self, text: str) -> str:
        prompt = f"""
Improve the following email draft. Keep the same meaning.
Make it clear, professional, and concise.
Return ONLY the improved email body text.

EMAIL:
{text}
"""
        return (await self.provider.generate_response([{"role": "user", "content": prompt}])).strip()

    async def summarize_email(self, text: str) -> str:
        prompt = f"""
Summarize this email in 3-6 bullet points.
Return ONLY the bullet list.

EMAIL:
{text}
"""
        return (await self.provider.generate_response([{"role": "user", "content": prompt}])).strip()

    async def generate_reply(self, email_text: str, instruction: str = "") -> str:
        prompt = f"""
Write a polite reply to this email.
If the user instruction is provided, follow it.
Return ONLY the reply body text.

EMAIL:
{email_text}

USER INSTRUCTION:
{instruction}
"""
        return (await self.provider.generate_response([{"role": "user", "content": prompt}])).strip()

    async def draft_email(self, *, to: str, topic: str) -> Dict[str, str]:
        prompt = f"""
Write a professional email.
Return ONLY JSON with keys: subject, body.

TO: {to}
TOPIC: {topic}
"""
        raw = (await self.provider.generate_response([{"role": "user", "content": prompt}])).strip()
        try:
            data = json.loads(raw)
        except Exception:
            return {"subject": f"Regarding {topic}".strip(), "body": raw or f"Hello,\n\nThis is about {topic}.\n"}

        subject = (data.get("subject") or f"Regarding {topic}").strip()
        body = (data.get("body") or "").strip() or f"Hello,\n\nThis is about {topic}.\n"
        return {"subject": subject, "body": body}


def ensure_email_ai(provider: Optional[BaseAIProvider]) -> Optional[EmailAIService]:
    if not provider:
        return None
    return EmailAIService(provider)

