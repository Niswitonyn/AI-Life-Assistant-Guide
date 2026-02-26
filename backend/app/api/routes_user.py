import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import create_token, hash_password, verify_password
from app.database.db import get_db
from app.models.user import User

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


def _upsert_google_user(db: Session, email: str, name: str, google_sub: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name=name or "",
            user_id=f"google:{google_sub}" if google_sub else f"user:{uuid4().hex}",
            password=None,
        )
        db.add(user)
    else:
        if name and not user.name:
            user.name = name
        if not user.user_id:
            user.user_id = f"google:{google_sub}" if google_sub else f"user:{uuid4().hex}"
    db.commit()
    db.refresh(user)
    return user


@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    normalized_email = (data.email or "").strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="email is required")

    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise HTTPException(status_code=409, detail="email already exists")

    user = User(
        email=normalized_email,
        password=hash_password(data.password),
        name=(data.name or "").strip(),
        user_id=f"user:{uuid4().hex}",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"status": "registered", "user_id": user.id}


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    normalized_email = (data.email or "").strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="email is required")

    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = create_token(str(user.id), email=user.email)
    return {
        "status": "success",
        "token": token,
        "user_id": user.id,
        "name": user.name,
    }


@router.post("/google")
def login_with_google(data: GoogleLoginRequest, db: Session = Depends(get_db)):
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip() or None

    try:
        payload = google_id_token.verify_oauth2_token(
            data.id_token,
            google_requests.Request(),
            google_client_id,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid google token")

    email = (payload.get("email") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    google_sub = (payload.get("sub") or "").strip()
    email_verified = bool(payload.get("email_verified"))

    if not email:
        raise HTTPException(status_code=400, detail="google account email missing")
    if not email_verified:
        raise HTTPException(status_code=401, detail="google email not verified")

    user = _upsert_google_user(db, email=email, name=name, google_sub=google_sub)
    token = create_token(str(user.id), email=user.email)

    return {
        "status": "success",
        "token": token,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
    }
