import os
import base64
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GmailAgent:

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def __init__(self):

        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        self.credentials_path = os.path.join(
            base_dir, "config", "credentials.json"
        )

        self.token_path = os.path.join(
            base_dir, "..", "data", "gmail_token.json"
        )

        self.service = self.authenticate()

    # -------------------------
    # AUTH
    # -------------------------
    def authenticate(self):

        creds = None

        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(
                self.token_path, self.SCOPES
            )

        if not creds or not creds.valid:

            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, self.SCOPES
            )

            creds = flow.run_local_server(port=0)

            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)

            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds)

        return service

    # -------------------------
    # READ LATEST EMAILS
    # -------------------------
    def get_latest_emails(self, max_results=5):

        results = (
            self.service.users()
            .messages()
            .list(userId="me", maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])

        emails = []

        for msg in messages:

            msg_data = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg["id"])
                .execute()
            )

            snippet = msg_data.get("snippet")

            emails.append(snippet)

        return emails

    # -------------------------
    # SEND EMAIL
    # -------------------------
    def send_email(self, to, subject, body):

        message = MIMEText(body)

        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode()

        send_message = {"raw": raw}

        self.service.users().messages().send(
            userId="me", body=send_message
        ).execute()

        return "Email sent successfully"
