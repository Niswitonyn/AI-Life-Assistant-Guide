from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import get_optional_current_user
from app.core.rag_logs import log_rag_event
from app.database.db import get_db
from app.database.models import Document, User
from app.rag.document_processor import DocumentProcessor, DocumentProcessorError
from app.services.event_bus import get_event_bus


router = APIRouter()


ALLOWED_EXTS = {".pdf", ".txt", ".docx"}
MAX_BYTES = int(os.getenv("DOCUMENT_MAX_BYTES", str(20 * 1024 * 1024)))  # 20MB default


def _safe_filename(name: str) -> str:
    base = (name or "").strip().replace("\\", "_").replace("/", "_")
    base = "".join(ch for ch in base if ch.isalnum() or ch in {" ", ".", "_", "-", "(", ")", "[", "]"}).strip()
    base = base or f"document_{int(time.time())}"
    # Avoid trailing dots/spaces (Windows)
    return base.strip(" .")


def _resolve_user_id(request_user_id: str, current_user: User | None) -> str:
    if current_user:
        return (current_user.user_id or "").strip() or "default"
    return (request_user_id or "").strip() or "default"


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = "default",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    started = time.perf_counter()
    req_user_id = _resolve_user_id(user_id, current_user)

    filename = _safe_filename(file.filename or "document")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=415, detail={"error": "unsupported_file_type", "allowed": sorted(ALLOWED_EXTS)})

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail={"error": "empty_file", "message": "Empty upload"})
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail={"error": "file_too_large", "max_bytes": MAX_BYTES})

    processor = DocumentProcessor()
    try:
        stored_path = processor.save_upload(content, filename=filename, user_id=req_user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "save_failed", "message": str(e)})

    log_rag_event("document.uploaded", {"user_id": req_user_id, "filename": filename, "bytes": len(content)})
    try:
        await get_event_bus().publish(
            "document_uploaded",
            {"user_id": req_user_id, "filename": filename, "size": len(content)},
        )
    except Exception:
        pass

    # Create DB row first (chunk_count patched after ingest).
    doc = Document(
        user_id=req_user_id,
        filename=filename,
        stored_path=str(stored_path),
        size_bytes=len(content),
        chunk_count=0,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        ingest = await asyncio.wait_for(
            asyncio.to_thread(processor.ingest_document, stored_path, user_id=req_user_id, document_id=doc.id),
            timeout=float(os.getenv("DOCUMENT_INGEST_TIMEOUT_S", "90")),
        )
    except asyncio.TimeoutError:
        log_rag_event("document.ingest_timeout", {"user_id": req_user_id, "filename": filename, "document_id": doc.id})
        raise HTTPException(status_code=504, detail={"error": "ingest_timeout", "message": "Document processing timed out"})
    except DocumentProcessorError as e:
        log_rag_event("document.ingest_failed", {"user_id": req_user_id, "filename": filename, "document_id": doc.id}, error=str(e))
        raise HTTPException(status_code=422, detail={"error": "ingest_failed", "message": str(e)})
    except Exception as e:
        log_rag_event("document.ingest_failed", {"user_id": req_user_id, "filename": filename, "document_id": doc.id}, error=str(e))
        raise HTTPException(status_code=500, detail={"error": "ingest_failed", "message": str(e)})

    doc.chunk_count = int(ingest.get("chunk_count", 0))
    db.add(doc)
    db.commit()
    try:
        await get_event_bus().publish(
            "document_ingested",
            {"user_id": req_user_id, "document_id": doc.id, "filename": filename, "chunk_count": doc.chunk_count},
        )
    except Exception:
        pass

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "status": "success",
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "size": doc.size_bytes,
            "upload_time": doc.upload_time.isoformat() if doc.upload_time else None,
            "chunk_count": doc.chunk_count,
        },
        "elapsed_ms": elapsed_ms,
    }


@router.get("/list")
async def list_documents(
    user_id: str = "default",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    req_user_id = _resolve_user_id(user_id, current_user)
    rows = (
        db.query(Document)
        .filter(Document.user_id == req_user_id)
        .order_by(Document.upload_time.desc())
        .limit(200)
        .all()
    )
    return {
        "status": "success",
        "documents": [
            {
                "id": r.id,
                "filename": r.filename,
                "size": r.size_bytes,
                "upload_time": r.upload_time.isoformat() if r.upload_time else None,
                "chunk_count": r.chunk_count,
            }
            for r in rows
        ],
    }
