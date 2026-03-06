import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import speech_recognition as sr
import pyttsx3
import requests

from app.router.smart_router import SmartRouter
from app.router.command_router import CommandRouter
from app.agents.browser_agent import BrowserAgent
from app.agents.file_agent import FileAgent
from app.automation.system_agent import SystemAgent


class VoiceAssistant:

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()

        # Agents
        self.browser = BrowserAgent()
        self.files = FileAgent()
        self.system = SystemAgent()

        # Routers
        # SmartRouter can touch Gmail auth; defer creation so backend startup
        # remains healthy even when Gmail tokens are stale.
        self.smart_router = None
        self.router = CommandRouter(
            system_agent=self.system,
            browser_agent=self.browser,
            file_agent=self.files,
        )

    def _get_smart_router(self):
        if self.smart_router is None:
            self.smart_router = SmartRouter()
        return self.smart_router

    # -------------------------
    # LISTEN
    # -------------------------
    def listen(self):
        with sr.Microphone() as source:
            print("Listening...")
            audio = self.recognizer.listen(source)

        try:
            text = self.recognizer.recognize_google(audio)
            print("You:", text)
            return text
        except Exception:
            return None

    # -------------------------
    # SPEAK
    # -------------------------
    def speak(self, text: str):
        print("Jarvis:", text)
        self.engine.say(text)
        self.engine.runAndWait()

    # -------------------------
    # AI FALLBACK
    # -------------------------
    def ask_ai(self, text: str):
        url = "http://127.0.0.1:8000/api/ai/chat"

        payload = {
            "provider": "ollama",
            "model": "llama3",
            "messages": [{"role": "user", "content": text}],
        }

        response = requests.post(url, json=payload)
        return response.json()["response"]

    # -------------------------
    # MAIN LOOP
    # -------------------------
    def run(self):
        self.speak("Voice assistant started")

        while True:
            text = self.listen()

            if not text:
                continue

            if "stop" in text.lower():
                self.speak("Goodbye")
                break

            try:
                # First try smart router (email + AI email)
                smart_router = self._get_smart_router()
                result = smart_router.route(text)

                # Email confirmation flow
                if isinstance(result, dict) and result.get("action") == "confirm_email":
                    to_email = result["to"]
                    subject = result["subject"]
                    body = result["body"]

                    self.speak(f"I have prepared an email to {to_email}")
                    self.speak(f"Subject: {subject}")
                    self.speak(body)

                    self.speak("Do you want me to send it?")

                    confirm = self.listen()

                    if confirm and any(word in confirm.lower() for word in ["yes", "send", "ok", "sure"]):
                        smart_router.gmail_agent.send_email(
                            to=to_email,
                            subject=subject,
                            body=body,
                        )
                        self.speak("Email sent successfully")
                    else:
                        self.speak("Email cancelled")

                    continue

                # If SmartRouter returned something useful
                if result and result != {"intent": "chat"}:
                    self.speak(str(result))
                    continue

                # Otherwise use command router
                data = smart_router.classify(text)
                result = self.router.execute(data)

                if result:
                    self.speak(str(result))
                else:
                    reply = self.ask_ai(text)
                    self.speak(reply)

            except Exception as e:
                print("Error:", e)
                self.speak("Something went wrong")


if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()