import requests
import json
import os

from app.agents.gmail_agent import GmailAgent

# MEMORY
from app.memory.memory_manager import MemoryManager
from app.database.db import SessionLocal


class SmartRouter:

    def __init__(self, user_id: str = "default", memory_manager=None):

        self.url = "http://127.0.0.1:8000/api/ai/chat"

        # Multi‑user
        self.user_id = user_id

        # Gmail per user
        self.gmail_agent = GmailAgent(user_id=user_id)

        # Memory
        if memory_manager:
            self.memory = memory_manager
        else:
            self.db = SessionLocal()
            self.memory = MemoryManager(self.db, user_id)

    # -------------------------
    # AI REQUEST HELPER (WITH CONTEXT)
    # -------------------------
    def _ask_ai(self, prompt: str):

        recent_conv = []
        memories = []

        if self.memory:
            recent = self.memory.get_recent_conversation(5)
            mems = self.memory.get_memories()

            recent_conv = [
                f"{c.role}: {c.message}" for c in recent
            ]

            memories = [
                m.content for m in mems
            ]

        context_block = f"""
USER MEMORIES:
{memories}

RECENT CONVERSATION:
{recent_conv}
"""

        full_prompt = context_block + "\n\n" + prompt

        payload = {
            "provider": "ollama",
            "model": "llama3",
            "messages": [
                {"role": "user", "content": full_prompt}
            ]
        }

        try:
            response = requests.post(self.url, json=payload, timeout=60)
            return response.json().get("response", "")

        except Exception:
            return ""

    # -------------------------
    # LOAD CONTACTS (fallback json)
    # -------------------------
    def load_contacts(self):

        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        contacts_path = os.path.join(base_dir, "data", "contacts.json")

        if os.path.exists(contacts_path):
            with open(contacts_path, "r") as f:
                return json.load(f)

        return {}

    # -------------------------
    # EMAIL GENERATION
    # -------------------------
    def generate_email(self, topic: str):

        prompt = f"""
Write a professional email about: {topic}.
Return JSON with keys: subject and body.
"""

        reply = self._ask_ai(prompt)

        try:
            data = json.loads(reply)
            subject = data.get("subject", topic)
            body = data.get("body", topic)
            return subject, body

        except Exception:
            return topic, f"Hello,\n\nThis is regarding {topic}.\n\nRegards"

    # -------------------------
    # EMAIL REPLY
    # -------------------------
    def generate_reply(self, original_text: str, instruction: str):

        prompt = f"""
You are replying to this email:

{original_text}

User wants to say:
{instruction}

Write a polite email reply.
Return only the reply text.
"""

        reply = self._ask_ai(prompt)

        return reply if reply else instruction

    # -------------------------
    # EMAIL SUMMARY
    # -------------------------
    def summarize_emails(self, emails):

        text_blob = "\n".join(emails)

        prompt = f"""
Summarize these emails clearly.

{text_blob}

Give short bullet points.
"""

        reply = self._ask_ai(prompt)

        return reply if reply else "Could not summarize emails"

    # -------------------------
    # EMAIL HANDLER
    # -------------------------
    def handle_email(self, command: str):

        command_lower = command.lower()

        # ---------- SUMMARIZE ----------
        if "summarize" in command_lower or "summary" in command_lower:

            emails = self.gmail_agent.get_latest_emails(5)

            if not emails:
                return "No emails found"

            return self.summarize_emails(emails)

        # ---------- READ ----------
        if "check" in command_lower or "read" in command_lower:
            return self.gmail_agent.get_latest_emails()

        words = command.split()
        contacts = self.load_contacts()

        # ---------- REPLY ----------
        if "reply" in command_lower:

            try:
                if "to" not in words:
                    return "Who should I reply to?"

                to_index = words.index("to") + 1
                name = words[to_index].lower()

                to_email = contacts.get(name, name)

                if "saying" in words:
                    say_index = words.index("saying") + 1
                    instruction = " ".join(words[say_index:])
                else:
                    instruction = "Thank you for your email."

                emails = self.gmail_agent.get_latest_emails(1)
                original = emails[0] if emails else ""

                body = self.generate_reply(original, instruction)

                return {
                    "action": "confirm_email",
                    "to": to_email,
                    "subject": "Re:",
                    "body": body
                }

            except Exception as e:
                return f"Reply failed: {str(e)}"

        # ---------- SEND ----------
        if "send" in command_lower:

            try:
                if "to" not in words:
                    return "Please specify recipient"

                to_index = words.index("to") + 1

                if to_index >= len(words):
                    return "Recipient not found"

                recipient = words[to_index].lower()
                to_email = contacts.get(recipient, recipient)

                if "about" in words:
                    about_index = words.index("about") + 1
                    topic = " ".join(words[about_index:])
                else:
                    topic = "Message from Assistant"

                subject, body = self.generate_email(topic)

                return {
                    "action": "confirm_email",
                    "to": to_email,
                    "subject": subject,
                    "body": body
                }

            except Exception as e:
                return f"Could not send email: {str(e)}"

        return "Email command not recognized"

    # -------------------------
    # CLASSIFIER
    # -------------------------
    def classify(self, text: str):

        text_lower = text.lower()

        if any(word in text_lower for word in
               ["email", "mail", "send", "check", "read",
                "reply", "summarize", "summary"]):
            return {"intent": "email"}

        prompt = f"""
You are an AI assistant that classifies user commands.

Return ONLY JSON.

Possible intents:
- system
- research
- file
- browser
- chat
- email

Now classify:
{text}
"""

        reply = self._ask_ai(prompt)

        try:
            return json.loads(reply)
        except Exception:
            return {"intent": "chat"}

    # -------------------------
    # MAIN ROUTE
    # -------------------------
    def route(self, text: str):

        # SAVE USER MESSAGE
        if self.memory:
            self.memory.save_conversation("user", text)

        intent_data = self.classify(text)
        intent = intent_data.get("intent")

        if intent == "email":
            result = self.handle_email(text)
        else:
            result = intent_data

        # SAVE ASSISTANT RESPONSE
        if self.memory:
            self.memory.save_conversation("assistant", str(result))

        return result