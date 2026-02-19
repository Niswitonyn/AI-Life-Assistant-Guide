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
        self.smart_router = SmartRouter()
        self.router = CommandRouter(
            system_agent=self.system,
            browser_agent=self.browser,
            file_agent=self.files
        )

    # -------------------------
    # LISTEN
    # -------------------------
    def listen(self):
        with sr.Microphone() as source:
            print("🎤 Listening...")
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
            "messages": [
                {"role": "user", "content": text}
            ]
        }

        response = requests.post(url, json=payload)

        return response.json()["response"]

    # -------------------------
    # MAIN LOOP
    # -------------------------
    def run(self):

        while True:

            text = self.listen()

            if not text:
                continue

            if "stop" in text.lower():
                break

            # ✅ Smart Router
            data = self.smart_router.classify(text)

            result = self.router.execute(data)

            if result:
                self.speak(str(result))
            else:
                reply = self.ask_ai(text)
                self.speak(reply)


if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()
