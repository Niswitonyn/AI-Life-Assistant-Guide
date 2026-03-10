import os
import base64
from email.mime.text import MIMEText
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

from app.config.paths import TOKENS_DIR, CREDENTIALS_FILE
from app.data.contact_manager import ContactManager


class GmailAgent:

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def __init__(self, user_id: str = "default"):

        self.user_id = user_id

        self.credentials_path = str(CREDENTIALS_FILE)
        self.token_path = TOKENS_DIR / f"{user_id}_gmail_token.json"

        self.token_path.parent.mkdir(parents=True, exist_ok=True)

        # Contact manager
        self.contacts = ContactManager()

        # Gmail service
        self.service = self.authenticate()

    # -------------------------
    # AUTHENTICATION
    # -------------------------
    def authenticate(self):
        creds = None

        # Validate credentials file exists before attempting auth
        if not Path(self.credentials_path).exists():
            raise FileNotFoundError(
                f"Google credentials file not found at: {self.credentials_path}\n"
                f"Please go to Settings and upload your credentials.json file from Google Cloud Console."
            )

        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self.token_path), self.SCOPES
                )
            except Exception as e:
                print(f"⚠️ Token file invalid, re-authenticating: {e}")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(self.token_path, "w") as token:
                        token.write(creds.to_json())
                except Exception as e:
                    print(f"⚠️ Token refresh failed: {e}")
                    creds = None

            if not creds or not creds.valid:
                raise PermissionError(
                    f"Gmail is not authenticated for user '{self.user_id}'.\n"
                    f"Please go to Settings → Connect Gmail and complete Google sign-in first."
                )

            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds)
        return service

    # -------------------------
    # GET EMAIL BY ID
    # -------------------------
    def get_email_by_id(self, message_id: str):

        try:
            msg_data = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id)
                .execute()
            )

            headers = msg_data.get("payload", {}).get("headers", [])

            subject = ""
            sender = ""

            for h in headers:
                if h["name"] == "Subject":
                    subject = h["value"]
                if h["name"] == "From":
                    sender = h["value"]

            snippet = msg_data.get("snippet", "")

            return {
                "subject": subject,
                "from": sender,
                "snippet": snippet
            }

        except Exception as e:
            print("❌ Error getting email:", e)
            return None

    # -------------------------
    # EXTRACT SENDER
    # -------------------------
    def extract_sender(self, msg_data):

        headers = msg_data.get("payload", {}).get("headers", [])

        for h in headers:
            if h["name"] == "From":
                return h["value"]

        return ""

    # -------------------------
    # READ LATEST EMAILS
    # -------------------------
    def get_latest_emails(self, max_results=5):

        try:
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

                # AUTO SAVE CONTACT
                sender = self.extract_sender(msg_data)
                if sender:
                    self.contacts.add_from_sender(sender)

            return emails

        except Exception as e:
            print("❌ Error reading emails:", e)
            return []

    # -------------------------
    # SEND EMAIL
    # -------------------------
    def send_email(self, to: str, subject: str, body: str):

        try:
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

        except Exception as e:
            print("❌ Send email error:", e)
            raise RuntimeError(str(e))

    # -------------------------
    # START GMAIL PUSH WATCH
    # -------------------------
    def start_watch(self, topic_name: str):

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
