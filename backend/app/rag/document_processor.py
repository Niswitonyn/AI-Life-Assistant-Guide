from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.config.paths import DATA_DIR
from app.core.rag_logs import log_rag_event
from app.rag.retriever import retriever


class DocumentProcessorError(RuntimeError):
    pass


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str


class DocumentProcessor:
    """
    Loads documents (PDF/TXT/DOCX), extracts text, chunks it, and ingests into the RAG store.
    """

    def __init__(
        self,
        *,
        chunk_tokens: int = 700,
        overlap_tokens: int = 120,
        max_chunks: int = 400,
    ):
        self.chunk_tokens = int(chunk_tokens)
        self.overlap_tokens = int(overlap_tokens)
        self.max_chunks = int(max_chunks)

    def documents_dir(self) -> Path:
        p = (DATA_DIR / "documents").resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save_upload(self, content: bytes, *, filename: str, user_id: str) -> Path:
        user = (user_id or "default").strip() or "default"
        base_dir = (self.documents_dir() / user).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)

        name = (filename or "document").strip()
        name = name.replace("\\", "_").replace("/", "_")
        target = (base_dir / name).resolve()
        if base_dir not in target.parents:
            raise DocumentProcessorError("Invalid filename/path.")

        # Avoid overwriting.
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            target = base_dir / f"{stem}_{int(time.time())}{suffix}"

        target.write_bytes(content)
        return target

    def ingest_document(self, path: Path | str, *, user_id: str, document_id: int | None = None) -> Dict:
        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_file():
            raise DocumentProcessorError("File not found.")

        ext = p.suffix.lower()
        if ext not in {".pdf", ".txt", ".docx"}:
            raise DocumentProcessorError(f"Unsupported file type: {ext}")

        text = self._extract_text(p)
        if not (text or "").strip():
            raise DocumentProcessorError("No text extracted from document.")

        chunks = self._chunk_text(text)
        if not chunks:
            raise DocumentProcessorError("Could not split document into chunks.")

        doc_name = p.name
        ingest_ids: List[str] = []
        for ch in chunks[: max(1, self.max_chunks)]:
            metadata = {
                "user_id": (user_id or "default").strip() or "default",
                "kind": "document_chunk",
                "document_name": doc_name,
                "document_id": document_id,
                "chunk_index": ch.index,
                "path": str(p),
            }
            ingest_ids.append(retriever.add_text(ch.text, metadata=metadata))

        log_rag_event(
            "document.ingested",
            {"user_id": user_id, "document_name": doc_name, "document_id": document_id, "chunk_count": len(ingest_ids)},
        )

        return {"document_name": doc_name, "chunk_count": len(ingest_ids), "chunk_ids": ingest_ids}

    # -------------------------
    # Text extraction
    # -------------------------

    def _extract_text(self, path: Path) -> str:
        ext = path.suffix.lower()
        if ext == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore")
        if ext == ".docx":
            return self._extract_docx(path)
        if ext == ".pdf":
            return self._extract_pdf(path)
        raise DocumentProcessorError(f"Unsupported file type: {ext}")

    def _extract_docx(self, path: Path) -> str:
        try:
            import docx
        except Exception as e:
            raise DocumentProcessorError(f"python-docx is required to process DOCX: {e}") from e

        try:
            d = docx.Document(str(path))
            parts: List[str] = []
            for para in d.paragraphs:
                t = (para.text or "").strip()
                if t:
                    parts.append(t)
            return "\n".join(parts)
        except Exception as e:
            raise DocumentProcessorError(f"Failed to parse DOCX: {e}") from e

    def _extract_pdf(self, path: Path) -> str:
        # Prefer PyPDF2 if available (explicit requirement). Keep error helpful.
        try:
            from PyPDF2 import PdfReader
        except Exception as e:
            raise DocumentProcessorError(
                "PyPDF2 is required to process PDF files. Install it (pip install PyPDF2)."
            ) from e

        try:
            reader = PdfReader(str(path))
            parts: List[str] = []
            for page in reader.pages:
                t = (page.extract_text() or "").strip()
                if t:
                    parts.append(t)
            return "\n".join(parts)
        except Exception as e:
            raise DocumentProcessorError(f"Failed to parse PDF: {e}") from e

    # -------------------------
    # Chunking
    # -------------------------

    def _chunk_text(self, text: str) -> List[Chunk]:
        words = [w for w in (text or "").split() if w.strip()]
        if not words:
            return []

        chunk_size = max(200, int(self.chunk_tokens))
        overlap = max(0, min(chunk_size - 1, int(self.overlap_tokens)))
        step = max(1, chunk_size - overlap)

        chunks: List[Chunk] = []
        i = 0
        idx = 0
        while i < len(words) and len(chunks) < max(1, self.max_chunks):
            piece = " ".join(words[i : i + chunk_size]).strip()
            if piece:
                chunks.append(Chunk(index=idx, text=piece))
                idx += 1
            i += step

        return chunks

