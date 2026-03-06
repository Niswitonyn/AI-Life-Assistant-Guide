from cryptography.fernet import Fernet
from pathlib import Path
from app.config.settings import settings


class EncryptionManager:
    """
    Handles encryption and decryption of sensitive data
    using Fernet symmetric encryption.
    """

    def __init__(self, key_path: str | Path):
        self.key_path = Path(key_path)
        self.key = self._load_or_create_key()
        self.cipher = Fernet(self.key)

    def _load_or_create_key(self) -> bytes:
        """
        Load encryption key from disk or create one if missing.
        """
        if self.key_path.exists():
            return self.key_path.read_bytes()

        # Generate new key
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        return key

    def encrypt(self, data: str) -> str:
        """
        Encrypt plaintext string.
        Returns base64 encoded encrypted string.
        """
        encrypted = self.cipher.encrypt(data.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted string back to plaintext.
        """
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        return decrypted.decode()


# Singleton instance for app-wide use
encryption_manager = EncryptionManager(settings.ENCRYPTION_KEY_PATH)
