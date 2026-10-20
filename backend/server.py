from __future__ import annotations

import io
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.documents.loader import SUPPORTED_EXTENSIONS

from . import rag
from .auth import (
    CurrentUser,
    create_access_token,
    create_user,
    get_user_by_email,
    verify_password,
)
from .config import settings
from .db import execute, query

app = FastAPI(title="DocuChat API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


class LoginPayload(BaseModel):
    email: str
    password: str


class RegisterPayload(BaseModel):
    email: str
    name: str
    password: str


def _public_user(row):
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "name": row["name"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
    }


@app.post("/api/auth/register")
def register(p: RegisterPayload):
    user = create_user(p.email, p.name, p.password)
    token = create_access_token(str(user["id"]))
    return {"accessToken": token, "user": _public_user(user)}


@app.post("/api/auth/login")
def login(p: LoginPayload):
    row = get_user_by_email(p.email)
    if not row or not verify_password(p.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(str(row["id"]))
    return {"accessToken": token, "user": _public_user(row)}


@app.get("/api/auth/me")
def me(user: CurrentUser):
    return _public_user(user)


# ---------------------------------------------------------------------------
# Document routes
# ---------------------------------------------------------------------------


@app.get("/api/documents")
def list_documents(user: CurrentUser):
    rows = (
        query(
            """
        SELECT id, user_id, filename, original_filename, file_size, mime_type,
               page_count, created_at
        FROM docuchat.documents
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
            (str(user["id"]),),
        )
        or []
    )
    return [
        {
            "id": str(r["id"]),
            "userId": str(r["user_id"]),
            "filename": r["filename"],
            "originalFilename": r["original_filename"],
            "fileSize": r["file_size"],
            "mimeType": r["mime_type"],
            "pageCount": r["page_count"],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@app.post("/api/documents/upload")
async def upload_document(user: CurrentUser, file: UploadFile = File(...)):
    filename = Path((file.filename or "").replace("\\", "/")).name
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported formats: PDF, DOCX, XLSX, XLS, CSV, TXT, MD.",
        )

    raw = await file.read(25 * 1024 * 1024 + 1)
    if not raw or len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "Choose a non-empty file up to 25 MB.")
    file_size = len(raw)
    suffix = ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        chunk_count, page_count = await run_in_threadpool(
            rag.process_upload,
            user_id=str(user["id"]),
            file_path=Path(tmp_path),
            original_filename=filename,
            file_size=file_size,
            mime=file.content_type or "application/octet-stream",
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logging.exception("Document processing failed")
        raise HTTPException(500, "Processing failed. Check the file and model configuration, then try again.") from exc
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "id": None,
        "filename": file.filename,
        "pageCount": page_count,
        "chunkCount": chunk_count,
    }


# ---------------------------------------------------------------------------
# Session routes
# ---------------------------------------------------------------------------


class SessionCreatePayload(BaseModel):
    documentId: str
    title: str | None = None


@app.get("/api/documents/{doc_id}/sessions")
def document_sessions(doc_id: str, user: CurrentUser):
    return _list_sessions(user, doc_id)


@app.get("/api/sessions")
def list_sessions(user: CurrentUser):
    return _list_sessions(user)


def _list_sessions(user, doc_id=None):
    rows = (
        query(
            """
        SELECT s.id, s.document_id, s.title, s.created_at, s.updated_at,
               (SELECT COUNT(*) FROM docuchat.messages m WHERE m.session_id = s.id) AS message_count
        FROM docuchat.sessions s
        WHERE s.user_id = %s AND (%s::uuid IS NULL OR s.document_id = %s::uuid)
        ORDER BY s.updated_at DESC
        """,
            (str(user["id"]), doc_id, doc_id),
        )
        or []
    )
    return [
        {
            "id": str(r["id"]),
            "userId": str(user["id"]),
            "documentId": str(r["document_id"]),
            "title": r["title"],
            "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            "updatedAt": r["updated_at"].isoformat() if r["updated_at"] else None,
            "messageCount": r["message_count"],
        }
        for r in rows
    ]


@app.post("/api/sessions")
def create_session(p: SessionCreatePayload, user: CurrentUser):
    # verify document ownership
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (p.documentId, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    title = p.title or f"Chat about {doc['original_filename']}"
    row = query(
        """
        INSERT INTO docuchat.sessions (id, user_id, document_id, title)
        VALUES (%s, %s, %s, %s)
        RETURNING id, title, document_id, created_at, updated_at
        """,
        (str(uuid.uuid4()), str(user["id"]), str(doc["id"]), title),
        one=True,
    )
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "documentId": str(row["document_id"]),
    }


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, user: CurrentUser):
    s = query(
        """
        SELECT s.id, s.user_id, s.document_id, s.title, s.created_at, s.updated_at,
               d.original_filename, d.page_count
        FROM docuchat.sessions s
        JOIN docuchat.documents d ON d.id = s.document_id
        WHERE s.id = %s AND s.user_id = %s
        """,
        (session_id, str(user["id"])),
        one=True,
    )
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    msgs = (
        query(
            "SELECT id, session_id, role, content, created_at FROM docuchat.messages "
            "WHERE session_id = %s ORDER BY created_at ASC",
            (session_id,),
        )
        or []
    )
    return {
        "id": str(s["id"]),
        "title": s["title"],
        "document": {
            "id": str(s["document_id"]),
            "originalFilename": s["original_filename"],
            "pageCount": s["page_count"],
        },
        "messages": [
            {
                "id": str(m["id"]),
                "sessionId": str(m["session_id"]),
                "role": m["role"],
                "content": m["content"],
                "createdAt": m["created_at"].isoformat() if m["created_at"] else None,
            }
            for m in msgs
        ],
    }


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, user: CurrentUser):
    rows = execute(
        "DELETE FROM docuchat.sessions WHERE id = %s AND user_id = %s",
        (session_id, str(user["id"])),
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Chat route (streaming)
# ---------------------------------------------------------------------------


class ChatPayload(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    mode: Literal["conversational", "agent"] = "conversational"
    model: str | None = None
    responseStyle: Literal["concise", "balanced", "detailed"] = "balanced"


def _row_to_msg(r):
    return {
        "id": str(r["id"]),
        "sessionId": str(r["session_id"]),
        "role": r["role"],
        "content": r["content"],
        "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
    }


@app.post("/api/sessions/{session_id}/chat")
def chat(session_id: str, payload: ChatPayload, user: CurrentUser):
    s = query(
        "SELECT document_id FROM docuchat.sessions WHERE id = %s AND user_id = %s",
        (session_id, str(user["id"])),
        one=True,
    )
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    doc_id = str(s["document_id"])

    model = payload.model or settings.DEFAULT_MODEL
    if model not in settings.CHAT_MODELS:
        raise HTTPException(422, "Model is not enabled on this server.")
    if not payload.message.strip():
        raise HTTPException(422, "Message cannot be blank.")
    history = rag.get_history(session_id)
    # Persist the user question after reading history to avoid duplicate turns.
    execute(
        "INSERT INTO docuchat.messages (id, session_id, role, content) VALUES (%s, %s, %s, %s)",
        (str(uuid.uuid4()), session_id, "user", payload.message),
    )
    execute(
        "UPDATE docuchat.sessions SET updated_at = now() WHERE id = %s",
        (session_id,),
    )
    gen = rag.stream_chat(
        doc_id=doc_id,
        query=payload.message,
        history=history,
        model_name=model,
        mode=payload.mode,
        response_style=payload.responseStyle,
    )

    def _event_stream():
        accumulated = io.StringIO()
        try:
            for chunk in gen:
                accumulated.write(chunk)
                yield chunk
        except Exception:  # noqa: BLE001
            logging.exception("Chat stream failed")
            yield "\n\n[STREAM ERROR] The model could not complete this response. Please try again."
        finally:
            # Persist the assistant turn once streaming is complete.
            text = accumulated.getvalue()
            execute(
                "INSERT INTO docuchat.messages (id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                (str(uuid.uuid4()), session_id, "assistant", text or "[no response]"),
            )

    return StreamingResponse(_event_stream(), media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/capabilities")
def capabilities(user: CurrentUser):
    return {
        "models": settings.CHAT_MODELS,
        "defaultModel": settings.DEFAULT_MODEL,
        "formats": sorted(SUPPORTED_EXTENSIONS),
        "maxUploadMB": 25,
    }


@app.get("/api/documents/{doc_id}/pages/{page}")
def read_document_page(doc_id: str, page: int, user: CurrentUser):
    doc = query("SELECT id FROM docuchat.documents WHERE id = %s AND user_id = %s", (doc_id, str(user["id"])), one=True)
    if not doc:
        raise HTTPException(404, "Document not found")
    from backend.documents.loader import load_document

    document = load_document(rag._pdf_path(doc_id))
    content = document.get_page(page)
    if content is None:
        raise HTTPException(404, "Page or section not found")
    return {"page": page, "totalPages": document.total_pages, "text": content.text, "filename": document.name}
