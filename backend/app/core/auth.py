import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.db import get_db
from app.models.user import User

SECRET_KEY = os.getenv("JWT_SECRET_KEY", getattr(settings, "JWT_SECRET_KEY", "")) or "change-this-jwt-secret"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_EXPIRE_MINUTES", str(getattr(settings, "JWT_EXPIRE_MINUTES", 10080)))
)  # 7 days
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    rounds = 100_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds)
    return f"pbkdf2_sha256${rounds}${salt}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    if not stored.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, stored)
    try:
        _, rounds, salt, expected = stored.split("$", 3)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(rounds),
        )
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, TypeError):
        return False


def create_token(user_id: str, email: str | None = None):
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        return None

    user_id = (payload.get("user_id") or payload.get("sub") or "").strip()
    if not user_id:
        return None

    if user_id.isdigit():
        return db.query(User).filter(User.id == int(user_id)).first()
    return db.query(User).filter(User.user_id == user_id).first()


def get_current_user(
    user: User | None = Depends(get_optional_current_user),
) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user
