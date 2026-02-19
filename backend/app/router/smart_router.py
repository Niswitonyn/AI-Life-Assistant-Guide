import requests
import json


class SmartRouter:

    def __init__(self):
        self.url = "http://127.0.0.1:8000/api/ai/chat"

    def classify(self, text: str):

        prompt = f"""
You are an AI assistant that classifies user commands.

Return ONLY JSON.

Possible intents:
- system
- research
- file
- browser
- chat

Fields:
intent, app, topic, length, read, filename

Examples:

User: open spotify
{{"intent":"system","app":"spotify"}}

User: research AI trends and give me 2 pages
{{"intent":"research","topic":"AI trends","length":"2 pages","read":false}}

User: find my resume file
{{"intent":"file","filename":"resume"}}

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
