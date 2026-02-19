import json
from pathlib import Path
from typing import Optional

from app.config.settings import settings
from app.security.encryption import encryption_manager


class KeyManager:
    """
    Handles secure storage and retrieval of API keys
    for different AI providers.
    """

    def __init__(self):
        self.file_path = Path(settings.KEYS_DIR) / "credentials.enc"

    def _load_storage(self) -> dict:
        """
        Load encrypted storage file.
        """
        if not self.file_path.exists():
            return {}

        encrypted_data = self.file_path.read_text()
        decrypted = encryption_manager.decrypt(encrypted_data)

        return json.loads(decrypted)

    def _save_storage(self, data: dict):
        """
        Save encrypted storage file.
        """
        json_data = json.dumps(data)
        encrypted = encryption_manager.encrypt(json_data)

        self.file_path.write_text(encrypted)

    # -------------------------

    def save_key(self, provider: str, api_key: str):
        """
        Save API key securely.
        """
        data = self._load_storage()
        data[provider] = api_key
        self._save_storage(data)

    def get_key(self, provider: str) -> Optional[str]:
        """
        Retrieve decrypted API key.
        """
        data = self._load_storage()
        return data.get(provider)

    def delete_key(self, provider: str):
        """
        Remove stored key.
        """
        data = self._load_storage()

        if provider in data:
            del data[provider]
            self._save_storage(data)


# Singleton instance
key_manager = KeyManager()
