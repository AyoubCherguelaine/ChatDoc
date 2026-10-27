"""
Ephemeral Document Store for DOC Tool.

Manages stateless, ephemeral document sessions with sliding inactivity TTL.
Documents are retained for a configurable period (default 10 minutes) without usage.
Every service invocation (OCR, extraction, pipeline run) touches the document and
resets the inactivity timer. If no requests are received within the TTL window,
the document files, index bundles, and temporary resources are automatically purged.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict

import pypdf
from backend.config import settings

logger = logging.getLogger("doc_tool.ephemeral")


@dataclass
class EphemeralDocument:
    doc_id: str
    user_id: str
    filename: str
    file_path: Path
    file_size: int
    mime_type: str
    page_count: int
    created_at: datetime
    last_accessed_at: datetime
    expires_at: datetime
    ttl_minutes: int
    chunk_count: int = 0

    @property
    def remaining_seconds(self) -> int:
        now = datetime.now(timezone.utc)
        diff = int((self.expires_at - now).total_seconds())
        return max(0, diff)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    def to_dict(self) -> dict:
        return {
            "documentId": self.doc_id,
            "filename": self.filename,
            "fileSize": self.file_size,
            "mimeType": self.mime_type,
            "pageCount": self.page_count,
            "chunkCount": self.chunk_count,
            "ttlMinutes": self.ttl_minutes,
            "remainingSeconds": self.remaining_seconds,
            "isExpired": self.is_expired,
            "createdAt": self.created_at.isoformat(),
            "lastAccessedAt": self.last_accessed_at.isoformat(),
            "expiresAt": self.expires_at.isoformat(),
        }


class EphemeralDocumentStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self._lock = threading.RLock()
        self._docs: Dict[str, EphemeralDocument] = {}
        self._base_dir = base_dir or (Path(settings.UPLOAD_DIR) / "ephemeral")
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def default_ttl_minutes(self) -> int:
        return max(1, getattr(settings, "DOC_TTL_MINUTES", 10))

    def register_file(
        self,
        doc_id: str,
        user_id: str,
        file_path: Path,
        filename: str,
        file_size: int,
        mime_type: str,
        page_count: int = 1,
        chunk_count: int = 0,
        ttl_minutes: Optional[int] = None,
    ) -> EphemeralDocument:
        """Register an existing file path as an ephemeral document session."""
        with self._lock:
            self.purge_expired()
            ttl = ttl_minutes if (ttl_minutes and ttl_minutes > 0) else self.default_ttl_minutes
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=ttl)

            doc = EphemeralDocument(
                doc_id=doc_id,
                user_id=user_id,
                filename=filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                page_count=page_count,
                chunk_count=chunk_count,
                created_at=now,
                last_accessed_at=now,
                expires_at=expires_at,
                ttl_minutes=ttl,
            )
            self._docs[doc_id] = doc
            logger.info(
                "Registered ephemeral doc %s ('%s', %d pages, TTL %d min)",
                doc_id,
                filename,
                page_count,
                ttl,
            )
            return doc

    def store_bytes(
        self,
        raw_bytes: bytes,
        filename: str,
        user_id: str = "guest",
        mime_type: str = "application/pdf",
        ttl_minutes: Optional[int] = None,
        doc_id: Optional[str] = None,
    ) -> EphemeralDocument:
        """Store raw bytes into the ephemeral storage directory and return session."""
        import uuid

        clean_filename = Path((filename or "document.pdf").replace("\\", "/")).name
        if not clean_filename or clean_filename in {".", ".."}:
            clean_filename = "document.pdf"

        target_id = doc_id or str(uuid.uuid4())
        doc_dir = self._base_dir / target_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        dest_path = doc_dir / clean_filename

        dest_path.write_bytes(raw_bytes)

        # Detect page count for PDFs
        page_count = 1
        if clean_filename.lower().endswith(".pdf") or "pdf" in mime_type.lower():
            try:
                reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
                page_count = max(1, len(reader.pages))
            except Exception:
                page_count = 1

        return self.register_file(
            doc_id=target_id,
            user_id=user_id,
            file_path=dest_path,
            filename=clean_filename,
            file_size=len(raw_bytes),
            mime_type=mime_type,
            page_count=page_count,
            ttl_minutes=ttl_minutes,
        )

    def get_and_touch(
        self, doc_id: str, extend_ttl: bool = True
    ) -> Optional[EphemeralDocument]:
        """
        Retrieve ephemeral document. If valid, touches the document and resets
        the inactivity expiration clock by `ttl_minutes`.
        If expired, removes the document and returns None.
        """
        with self._lock:
            doc = self._docs.get(doc_id)
            if not doc:
                # Fallback: check if the file exists on disk within ephemeral directory
                potential_dir = self._base_dir / doc_id
                if potential_dir.exists() and potential_dir.is_dir():
                    files = list(potential_dir.glob("*"))
                    if files:
                        target_file = files[0]
                        # Adopt it with fresh TTL
                        doc = self.register_file(
                            doc_id=doc_id,
                            user_id="ephemeral",
                            file_path=target_file,
                            filename=target_file.name,
                            file_size=target_file.stat().st_size,
                            mime_type="application/pdf" if target_file.suffix == ".pdf" else "application/octet-stream",
                        )

            if not doc:
                return None

            if doc.is_expired:
                logger.info("Ephemeral document %s expired after inactivity.", doc_id)
                self._purge_single(doc_id)
                return None

            if extend_ttl:
                now = datetime.now(timezone.utc)
                doc.last_accessed_at = now
                doc.expires_at = now + timedelta(minutes=doc.ttl_minutes)
                logger.debug(
                    "Touched ephemeral doc %s: TTL renewed for %d min (expires at %s)",
                    doc_id,
                    doc.ttl_minutes,
                    doc.expires_at.isoformat(),
                )

            return doc

    def _purge_single(self, doc_id: str) -> None:
        doc = self._docs.pop(doc_id, None)
        # Remove directory
        doc_dir = self._base_dir / doc_id
        if doc_dir.exists():
            try:
                shutil.rmtree(doc_dir, ignore_errors=True)
            except Exception as exc:
                logger.warning("Failed removing ephemeral directory for %s: %s", doc_id, exc)

        # Remove from RAG registry if loaded
        try:
            from backend import rag
            with rag._lock:
                rag._registry.pop(doc_id, None)
        except Exception:
            pass

        # Cleanup DB references if present
        try:
            from backend.db import get_conn
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM docuchat.chunks WHERE document_id = %s", (doc_id,))
                    cur.execute("DELETE FROM docuchat.documents WHERE id = %s", (doc_id,))
        except Exception:
            pass

    def purge_expired(self) -> int:
        """Purge all documents whose inactivity timeout has expired."""
        with self._lock:
            now = datetime.now(timezone.utc)
            expired_ids = [
                d_id for d_id, doc in self._docs.items() if now >= doc.expires_at
            ]
            for d_id in expired_ids:
                self._purge_single(d_id)
            if expired_ids:
                logger.info("Purged %d expired ephemeral documents: %s", len(expired_ids), expired_ids)
            return len(expired_ids)

    def delete(self, doc_id: str) -> bool:
        """Explicitly delete an ephemeral document immediately."""
        with self._lock:
            if doc_id in self._docs or (self._base_dir / doc_id).exists():
                self._purge_single(doc_id)
                return True
            return False

    def list_active(self) -> list[EphemeralDocument]:
        with self._lock:
            self.purge_expired()
            return list(self._docs.values())


# Global singleton instance
ephemeral_store = EphemeralDocumentStore()

