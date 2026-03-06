class EmailNotifier:

    def __init__(self, gmail_agent=None, voice_assistant=None, ai_url=None):
        self.gmail_agent = gmail_agent
        self.voice_assistant = voice_assistant
        self.ai_url = ai_url

    def notify_new_email(self, message_id: str):

        if not self.gmail_agent:
            print("⚠️ No Gmail agent configured")
            return

        try:
            message = self.gmail_agent.get_email_by_id(message_id)

            if not message:
                return

            subject = message.get("subject", "New Email")
            sender = message.get("from", "Unknown sender")

            text = f"You received a new email from {sender}. Subject: {subject}"

            print("📧 Notification:", text)

            if self.voice_assistant:
                self.voice_assistant.speak(text)

        except Exception as e:
            print("❌ Notification error:", e)