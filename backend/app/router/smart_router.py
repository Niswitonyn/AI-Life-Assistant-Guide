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
    # EMAIL HANDLER
    # -------------------------
    def handle_email(self, command: str):

        command_lower = command.lower()

        # READ EMAIL
        if "check" in command_lower or "read" in command_lower:
            emails = self.gmail_agent.get_latest_emails()
            return emails

        # SEND EMAIL
        if "send" in command_lower:

            try:
                words = command.split()

                contacts = self.load_contacts()

                # find recipient
                to_index = words.index("to") + 1
                recipient = words[to_index].lower()

                # name → email mapping
                if recipient in contacts:
                    to_email = contacts[recipient]
                else:
                    to_email = recipient  # assume full email spoken

                # subject/body
                if "about" in words:
                    about_index = words.index("about") + 1
                    subject = " ".join(words[about_index:])
                else:
                    subject = "Message from Assistant"

                body = subject

                # 🔥 RETURN CONFIRMATION DATA
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
    # CLASSIFIER (AI INTENT)
    # -------------------------
    def classify(self, text: str):

        # EMAIL SHORT‑CIRCUIT
        if "email" in text.lower() or "mail" in text.lower():
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

Fields:
intent, app, topic, length, read, filename

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

        response = requests.post(self.url, json=payload)

        reply = response.json()["response"]

        try:
            return json.loads(reply)
        except:
            return {"intent": "chat"}

    # -------------------------
    # MAIN ROUTE FUNCTION
    # -------------------------
    def route(self, text: str):

        intent_data = self.classify(text)

        intent = intent_data.get("intent")

        if intent == "email":
            return self.handle_email(text)

        return intent_data
