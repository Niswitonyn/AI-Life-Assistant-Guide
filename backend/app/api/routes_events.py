from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.responses import StreamingResponse

from app.services.event_bus import get_event_bus


router = APIRouter()


async def _sse_stream() -> AsyncIterator[str]:
    bus = get_event_bus()
    q = await bus.subscribe()
    try:
        while True:
            event = await q.get()
            payload = json.dumps({"type": event.type, "data": event.data}, ensure_ascii=False)
            yield f"event: {event.type}\n"
            yield f"data: {payload}\n\n"
    except asyncio.CancelledError:
        return
    finally:
        await bus.unsubscribe(q)


@router.get("/stream")
async def stream_events():
    return StreamingResponse(_sse_stream(), media_type="text/event-stream")


@router.websocket("/ws")
async def websocket_events(ws: WebSocket):
    await ws.accept()
    bus = get_event_bus()
    q = await bus.subscribe()
    try:
        while True:
            event = await q.get()
            await ws.send_text(json.dumps({"type": event.type, "data": event.data}, ensure_ascii=False))
    except WebSocketDisconnect:
        return
    except Exception:
        return
    finally:
        try:
            await bus.unsubscribe(q)
        except Exception:
            pass
