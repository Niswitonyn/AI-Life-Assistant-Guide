import json
import re
from app.config.paths import CONTACTS_FILE


class ContactManager:

    def __init__(self):
        self.contacts_path = CONTACTS_FILE

        self.contacts_path.parent.mkdir(parents=True, exist_ok=True)

    def load_contacts(self):

        if self.contacts_path.exists():
            with open(self.contacts_path, "r") as f:
                return json.load(f)

        return {}

    def save_contacts(self, contacts):

        with open(self.contacts_path, "w") as f:
            json.dump(contacts, f, indent=2)

    # -------------------------
    # AUTO STORE FROM EMAIL
    # -------------------------
    def add_from_sender(self, sender):

        contacts = self.load_contacts()

        # Extract email + name
        match = re.search(r"(.*)<(.+)>", sender)

        if match:
            name = match.group(1).strip().lower()
            email = match.group(2).strip()
        else:
            email = sender.strip()
            name = email.split("@")[0].lower()

        if name not in contacts:
            contacts[name] = email
            self.save_contacts(contacts)
            print(f"✅ Saved contact: {name} → {email}")
