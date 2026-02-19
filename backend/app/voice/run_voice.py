import sys
import os
from urllib import response

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import requests

from speech_to_text import SpeechToText
from text_to_speech import TextToSpeech

from app.router.command_router import CommandRouter
from app.agents.browser_agent import BrowserAgent
from app.agents.file_agent import FileAgent
from app.automation.system_agent import SystemAgent
from app.memory.memory_service import MemoryService
from app.database.db import SessionLocal






class VoiceAssistant:

    def __init__(self):
        self.stt = SpeechToText()
        self.tts = TextToSpeech()

        # Agents    
        self.browser = BrowserAgent()   
        self.files = FileAgent()
        self.system = SystemAgent()

        self.db = SessionLocal()
        self.memory = MemoryService(self.db)



        # Router
        self.router = CommandRouter(
            system_agent=self.system,
            browser_agent=self.browser,
            file_agent=self.files
        )

        def ask_ai(self, text: str):

            # ✅ save user message
            self.memory.save_message("user", text)

            # ✅ load recent conversation
            history = self.memory.get_recent_messages(limit=10)

            url = "http://127.0.0.1:8000/api/ai/chat"

            payload = {
                "provider": "ollama",
                "model": "llama3",
                "messages": history
            }

            response = requests.post(url, json=payload)

            reply = response.json()["response"]

            # ✅ save assistant reply
            self.memory.save_message("assistant", reply)

            return reply


        while True:
            text = self.stt.listen()

            if not text:
                continue

            if "stop" in text.lower():
                break

            # ROUTER handles everything
            result = self.router.route(text)

            if result:
                self.tts.speak(str(result))
            else:
                # fallback AI chat
                reply = self.ask_ai(text)
                self.tts.speak(reply)


if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()
