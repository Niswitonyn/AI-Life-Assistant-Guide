import os
import base64
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

from app.data.contact_manager import ContactManager


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

        # ✅ Contact manager initialized correctly
        self.contacts = ContactManager()

        self.service = self.authenticate()

    # -------------------------
    # AUTHENTICATION
    # -------------------------
    def authenticate(self):

        creds = None

        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(
                self.token_path, self.SCOPES
            )

        if not creds or not creds.valid:

            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())

            else:
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
    # EXTRACT SENDER INFO
    # -------------------------
    def extract_sender(self, msg_data):

        headers = msg_data.get("payload", {}).get("headers", [])

        sender = ""

        for h in headers:
            if h["name"] == "From":
                sender = h["value"]
                break

        return sender

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

            snippet = msg_data.get("snippet", "")
            emails.append(snippet)

            # ✅ AUTO SAVE CONTACT
            sender = self.extract_sender(msg_data)
            if sender:
                self.contacts.add_from_sender(sender)

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

    # -------------------------
    # START GMAIL PUSH WATCH
    # -------------------------
    def start_watch(self, topic_name):

        request = {
            "labelIds": ["INBOX"],
            "topicName": topic_name
        }

        response = self.service.users().watch(
            userId="me",
            body=request
        ).execute()

        print("✅ Gmail watch started:", response)

        return response

    # -------------------------
    # STOP WATCH
    # -------------------------
    def stop_watch(self):

        response = self.service.users().stop(
            userId="me"
        ).execute()

        print("🛑 Gmail watch stopped")

        return response