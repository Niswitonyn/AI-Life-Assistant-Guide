from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from google.oauth2.credentials import Credentials

from app.config.paths import TOKENS_DIR
from app.security.encryption import encryption_manager


@dataclass(frozen=True)
class TokenPaths:
    plaintext: Path
    encrypted: Path


def token_paths(user_id: str) -> TokenPaths:
    uid = (user_id or "").strip() or "default"
    return TokenPaths(
        plaintext=TOKENS_DIR / f"{uid}_gmail_token.json",
        encrypted=TOKENS_DIR / f"{uid}_gmail_token.enc",
    )


def load_gmail_credentials(user_id: str, scopes: Optional[Iterable[str]] = None) -> Credentials:
    """
    Load Gmail OAuth credentials for a user.

    Security:
    - Prefers encrypted token storage (`*.enc`).
    - If a legacy plaintext json token exists, migrates it to encrypted storage and removes plaintext.
    """
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    paths = token_paths(user_id)

    if paths.encrypted.exists():
        decrypted = encryption_manager.decrypt(paths.encrypted.read_text(encoding="utf-8"))
        info = json.loads(decrypted)
        return Credentials.from_authorized_user_info(info, scopes=scopes)

    if paths.plaintext.exists():
        info = json.loads(paths.plaintext.read_text(encoding="utf-8"))
        save_gmail_credentials(user_id, Credentials.from_authorized_user_info(info, scopes=scopes))
        # Remove plaintext token after migration.
        paths.plaintext.unlink(missing_ok=True)
        return Credentials.from_authorized_user_info(info, scopes=scopes)

    raise FileNotFoundError(f"No Gmail token found for user '{user_id}'. Please connect Gmail first.")


def save_gmail_credentials(user_id: str, creds: Credentials) -> str:
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    paths = token_paths(user_id)

    # Store encrypted json (no plaintext tokens).
    encrypted = encryption_manager.encrypt(creds.to_json())
    paths.encrypted.write_text(encrypted, encoding="utf-8")

    # Best-effort cleanup legacy plaintext.
    paths.plaintext.unlink(missing_ok=True)
    return str(paths.encrypted)

