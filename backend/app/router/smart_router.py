import requests
import json
import os

from app.agents.gmail_agent import GmailAgent


class SmartRouter:

    def __init__(self):
        self.url = "http://127.0.0.1:8000/api/ai/chat"
        self.gmail_agent = GmailAgent()

    # -------------------------
    # LOAD CONTACTS
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
    # AI EMAIL GENERATION
    # -------------------------
    def generate_email(self, topic: str):

        prompt = f"""
Write a professional email about: {topic}.
Return JSON with keys: subject and body.
"""

        payload = {
            "provider": "ollama",
            "model": "llama3",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            response = requests.post(self.url, json=payload)
            reply = response.json().get("response", "")

            data = json.loads(reply)

            subject = data.get("subject", topic)
            body = data.get("body", topic)

            return subject, body

        except Exception:
            subject = topic
            body = f"Hello,\n\nThis is regarding {topic}.\n\nRegards"
            return subject, body

    # -------------------------
    # AI REPLY GENERATION
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

        payload = {
            "provider": "ollama",
            "model": "llama3",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            response = requests.post(self.url, json=payload)
            return response.json().get("response", instruction)

        except Exception:
            return instruction

    # -------------------------
    # AI SUMMARY
    # -------------------------
    def summarize_emails(self, emails):

        text_blob = "\n".join(emails)

        prompt = f"""
Summarize these emails clearly.

{text_blob}

Give short bullet points.
"""

        payload = {
            "provider": "ollama",
            "model": "llama3",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            response = requests.post(self.url, json=payload)
            return response.json().get("response", "No summary available")

        except Exception:
            return "Could not summarize emails"

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

                # instruction
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

                # topic
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

        payload = {
            "provider": "ollama",
            "model": "llama3",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        try:
            response = requests.post(self.url, json=payload)
            reply = response.json().get("response", "")
            return json.loads(reply)

        except Exception:
            return {"intent": "chat"}

    # -------------------------
    # MAIN ROUTE
    # -------------------------
    def route(self, text: str):

        intent_data = self.classify(text)
        intent = intent_data.get("intent")

        if intent == "email":
            return self.handle_email(text)

        return intent_data