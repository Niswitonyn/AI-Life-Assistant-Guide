import os
import json
import re


class ContactManager:

    def __init__(self):

        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        self.contacts_path = os.path.join(
            base_dir, "data", "contacts.json"
        )

        os.makedirs(os.path.dirname(self.contacts_path), exist_ok=True)

    def load_contacts(self):

        if os.path.exists(self.contacts_path):
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