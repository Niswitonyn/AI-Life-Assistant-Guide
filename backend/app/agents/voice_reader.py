import pyttsx3


class VoiceReader:

    def __init__(self):
        self.engine = pyttsx3.init()

    def read_text(self, text):
        self.engine.say(text)
        self.engine.runAndWait()
