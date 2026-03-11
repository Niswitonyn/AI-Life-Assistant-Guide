import requests

from app.config.settings import settings
from app.voice.speech_to_text import SpeechToText
from app.voice.text_to_speech import TextToSpeech


class VoiceAssistant:
    def __init__(self):
        self.stt = SpeechToText()
        self.tts = TextToSpeech()

    def ask_ai(self, text: str) -> str:
        payload = {
            "provider": settings.DEFAULT_PROVIDER,
            "model": settings.DEFAULT_MODEL,
            "user_id": "default",
            "messages": [{"role": "user", "content": text}],
        }

        response = requests.post(
            "http://127.0.0.1:8000/api/ai/chat",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        return response.json().get("response", "Okay")

    def run(self):
        while True:
            text = self.stt.listen()
            if not text:
                continue

            if "stop" in text.lower():
                break

            reply = self.ask_ai(text)
            self.tts.speak(reply)


if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()
