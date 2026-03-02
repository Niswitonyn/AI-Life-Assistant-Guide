from datetime import datetime
from typing import List, Dict

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from app.config.paths import TOKENS_DIR


class CalendarAgent:
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id

        self.token_path = TOKENS_DIR / f"{user_id}_gmail_token.json"

        if not os.path.exists(self.token_path):
            raise RuntimeError("No Gmail token found. Please connect Gmail first.")

        self.service = self.authenticate()

    def authenticate(self):
        creds = Credentials.from_authorized_user_file(
            str(self.token_path)
        )

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(self.token_path, "w", encoding="utf-8") as token:
                    token.write(creds.to_json())
            else:
                raise RuntimeError("Token is invalid and cannot be refreshed.")

        return build("calendar", "v3", credentials=creds)

    def get_upcoming_events(self, max_results: int = 10) -> List[Dict]:
        now = datetime.utcnow().isoformat() + "Z"

        events_result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])

        return [
            {
                "id": event.get("id"),
                "summary": event.get("summary", "(No title)"),
                "start": (event.get("start", {}).get("dateTime")
                          or event.get("start", {}).get("date")),
                "end": (event.get("end", {}).get("dateTime")
                        or event.get("end", {}).get("date")),
                "htmlLink": event.get("htmlLink"),
            }
            for event in events
        ]
