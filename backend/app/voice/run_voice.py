import requests

from app.agents.browser_agent import BrowserAgent
from app.agents.file_agent import FileAgent
from app.automation.system_agent import SystemAgent
from app.database.db import SessionLocal
from app.memory.memory_service import MemoryService
from app.router.command_router import CommandRouter
from app.voice.speech_to_text import SpeechToText
from app.voice.text_to_speech import TextToSpeech


class VoiceAssistant:
    def __init__(self):
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.browser = BrowserAgent()
        self.files = FileAgent()
        self.system = SystemAgent()
        self.db = SessionLocal()
        self.memory = MemoryService(self.db)
        self.router = CommandRouter(
            system_agent=self.system,
            browser_agent=self.browser,
            file_agent=self.files,
        )

    def ask_ai(self, text: str) -> str:
        self.memory.save_message("default", "user", text)
        history = self.memory.get_recent_messages(user_id="default", limit=10)

        payload = {
            "provider": "ollama",
            "model": "llama3",
            "user_id": "default",
            "messages": history,
        }

        response = requests.post(
            "http://127.0.0.1:8000/api/ai/chat",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        reply = response.json().get("response", "Okay")
        self.memory.save_message("default", "assistant", reply)
        return reply

    def run(self):
        try:
            while True:
                text = self.stt.listen()
                if not text:
                    continue

                if "stop" in text.lower():
                    break

                result = self.router.route(text)
                if result:
                    self.tts.speak(str(result))
                    continue

                reply = self.ask_ai(text)
                self.tts.speak(reply)
        finally:
            self.db.close()


if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()
