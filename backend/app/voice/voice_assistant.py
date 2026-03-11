import requests

from app.config.settings import settings
from app.voice.speech_to_text import SpeechToText, SpeechToTextError
from app.voice.text_to_speech import speak as tts_speak


class VoiceAssistant:

    def __init__(self):
        self.stt = SpeechToText()

    # -------------------------
    # LISTEN
    # -------------------------
    def listen(self):
        try:
            res = self.stt.transcribe_microphone()
            text = (res.text or "").strip()
            if text:
                print("You:", text)
            return text or None
        except SpeechToTextError:
            return None

    # -------------------------
    # SPEAK
    # -------------------------
    def speak(self, text: str):
        print("Jarvis:", text)
        tts_speak(text)

    # -------------------------
    # AI FALLBACK
    # -------------------------
    def ask_ai(self, text: str):
        url = "http://127.0.0.1:8000/api/voice/input"
        payload = {"provider": settings.DEFAULT_PROVIDER, "model": settings.DEFAULT_MODEL, "text": text}
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return (data.get("response_text") or "").strip() or "Okay."

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
                # Unified: always send voice text through the backend brain controller (/api/ai/chat).
                reply = self.ask_ai(text)
                self.speak(reply)

            except Exception as e:
                print("Error:", e)
                self.speak("Something went wrong")


if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()
