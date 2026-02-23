from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.user import User
from app.core.auth import create_token   # ✅ JWT token creator

router = APIRouter()


# -------------------------
# DB SESSION
# -------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# REGISTER
# -------------------------
@router.post("/register")
def register(data: dict, db: Session = Depends(get_db)):

    user = User(
        email=data["email"],
        password=data["password"],
        name=data.get("name", "")
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "status": "registered",
        "user_id": user.id
    }


# -------------------------
# LOGIN
# -------------------------
@router.post("/login")
def login(data: dict, db: Session = Depends(get_db)):

    user = db.query(User).filter(
        User.email == data["email"],
        User.password == data["password"]
    ).first()

    if not user:
        return {"error": "invalid credentials"}

    # ✅ Create session token
    token = create_token(str(user.id))

    return {
        "status": "success",
        "token": token,
        "user_id": user.id,
        "name": user.name
    }