from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_optional_current_user
from app.database.db import get_db
from app.database.models import User
from app.learning.behavior_tracker import BehaviorTracker
from app.learning.suggestion_engine import SuggestionEngine
from app.learning.user_preferences import UserPreferences


router = APIRouter()


def _resolve_user_id(request_user_id: str, current_user: User | None) -> str:
    if current_user:
        return (current_user.user_id or "").strip() or "default"
    return (request_user_id or "").strip() or "default"


class PrefSetRequest(BaseModel):
    user_id: str = "default"
    key: str = Field(min_length=1, max_length=64)
    value: Optional[str] = None


class TrackingRequest(BaseModel):
    user_id: str = "default"
    enabled: bool = True


class ResetRequest(BaseModel):
    user_id: str = "default"
    reset_preferences: bool = True
    reset_behavior: bool = True


@router.get("/preferences")
def get_preferences(
    user_id: str = "default",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    uid = _resolve_user_id(user_id, current_user)
    prefs = UserPreferences(db, uid).as_dict()
    return {"status": "success", "user_id": uid, "preferences": prefs}


@router.post("/preferences")
def set_preference(
    req: PrefSetRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    # Mutations require auth.
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    uid = _resolve_user_id(req.user_id, current_user)
    UserPreferences(db, uid).set(req.key, req.value)
    return {"status": "success"}


@router.post("/tracking")
def set_tracking(
    req: TrackingRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    uid = _resolve_user_id(req.user_id, current_user)
    UserPreferences(db, uid).set(BehaviorTracker.PREF_ENABLED, "true" if req.enabled else "false")
    return {"status": "success", "enabled": bool(req.enabled)}


@router.post("/reset")
def reset_learning(
    req: ResetRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    uid = _resolve_user_id(req.user_id, current_user)
    deleted = {}
    if req.reset_behavior:
        from app.database.models import UserBehavior

        count = db.query(UserBehavior).filter(UserBehavior.user_id == uid).delete()
        db.commit()
        deleted["behavior"] = int(count)
    if req.reset_preferences:
        deleted["preferences"] = UserPreferences(db, uid).reset()
    return {"status": "success", "deleted": deleted}


@router.get("/suggestions")
def get_suggestions(
    user_id: str = "default",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    uid = _resolve_user_id(user_id, current_user)
    sugg = SuggestionEngine(db, uid).get_suggestions(limit=5)
    return {"status": "success", "user_id": uid, "suggestions": sugg}
