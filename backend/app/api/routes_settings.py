from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.security.key_manager import key_manager

router = APIRouter()


# -------------------------
# Request Models
# -------------------------

class APIKeyRequest(BaseModel):
    provider: str
    api_key: str


# -------------------------
# Routes
# -------------------------

@router.post("/save-key")
async def save_api_key(request: APIKeyRequest):
    """
    Save API key securely (encrypted).
    """

    try:
        provider = request.provider.lower()
        key_manager.save_key(provider, request.api_key)

        return {"status": "success", "message": "API key saved"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get-key/{provider}")
async def get_api_key(provider: str):
    """
    Check if API key exists (safe — does NOT return key).
    """

    try:
        provider = provider.lower()
        key = key_manager.get_key(provider)

        if not key:
            return {"status": "not_found"}

        return {"status": "found"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete-key/{provider}")
async def delete_api_key(provider: str):
    """
    Delete stored API key.
    """

    try:
        provider = provider.lower()
        key_manager.delete_key(provider)

        return {"status": "deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
