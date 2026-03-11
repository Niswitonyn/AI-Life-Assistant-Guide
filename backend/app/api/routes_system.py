from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.monitoring.health_monitor import health_monitor
from app.monitoring.status_registry import status_registry


router = APIRouter()


@router.get("/system/health")
async def system_health() -> Dict[str, Any]:
    snapshot = status_registry.get_snapshot()
    alerts = status_registry.get_alerts(limit=10)
    snapshot["alerts"] = alerts
    snapshot["monitor_running"] = health_monitor.is_running
    return snapshot


class RestartRequest(BaseModel):
    component: str


@router.post("/system/restart")
async def system_restart(req: RestartRequest, user=Depends(get_current_user)) -> Dict[str, Any]:
    _ = user  # authenticated
    comp = (req.component or "").strip()
    if not comp:
        raise HTTPException(status_code=400, detail="component is required")
    return await health_monitor.restart_component(comp)

