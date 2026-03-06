import requests


class ReportAI:

    def generate(self, topic, content, length="1 page"):

        prompt = f"""
        Create a {length} report about: {topic}

        {content}
        """

        url = "http://127.0.0.1:8000/api/ai/chat"

        payload = {
            "provider": "ollama",
            "model": "llama3",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        response = requests.post(url, json=payload)

        return response.json()["response"]
