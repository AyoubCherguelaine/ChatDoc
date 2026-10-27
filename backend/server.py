from __future__ import annotations

import io
import json
import logging
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.billing import (
    INITIAL_TRIAL_CREDITS,
    SERVICE_PRICING,
    CompanyAccount,
    InsufficientCreditsError,
    billing_service,
)
from backend.documents.loader import SUPPORTED_EXTENSIONS
from backend.jobs import job_queue, start_background_worker
from backend.mcp.server import mcp_server
from backend.storage import storage_service
from backend.v1.routes import (
    _extract_json_from_text,
    extract_structured_data,
    router as v1_router,
)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting DOCTool background job queue worker...")
    start_background_worker()
    yield

app = FastAPI(title="DOCTool API", version="0.1.0", lifespan=lifespan)

app.include_router(v1_router)
app.mount("/mcp", mcp_server.sse_app())

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all unhandled exception handler to escape crashes and keep API responsive."""
    logging.exception("Unhandled server exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred during processing. The system remains online.",
            "error": str(exc),
            "path": request.url.path,
        },
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
async def upload_document(
    user: CurrentUser,
    file: UploadFile = File(...),
    max_pages: Optional[int] = Form(None),
):
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

    # Pre-validation for PDF page count limit if max_pages is specified
    if ext == ".pdf" and max_pages is not None and max_pages > 0:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw))
            pdf_page_count = len(reader.pages)
            if pdf_page_count > max_pages:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"This document has {pdf_page_count} pages, which exceeds the maximum limit of {max_pages} pages for chat. Please upload a document with at most {max_pages} pages.",
                )
        except HTTPException:
            raise
        except Exception as exc:
            logging.debug("Pre-flight PDF page check skipped: %s", exc)

    suffix = ext
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        upload_result = await run_in_threadpool(
            rag.process_upload,
            user_id=str(user["id"]),
            file_path=Path(tmp_path),
            original_filename=filename,
            file_size=file_size,
            mime=file.content_type or "application/octet-stream",
        )
        chunk_count, page_count = upload_result[0], upload_result[1]
        doc_id = getattr(upload_result, "document_id", None)

        if max_pages is not None and max_pages > 0 and page_count > max_pages:
            # Cleanup document
            try:
                from backend.db import get_conn
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM docuchat.chunks WHERE document_id = %s", (doc_id,))
                        cur.execute("DELETE FROM docuchat.documents WHERE id = %s", (doc_id,))
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"This document has {page_count} pages, which exceeds the maximum limit of {max_pages} pages for chat. Please upload a document with at most {max_pages} pages.",
            )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Document processing failed")
        raise HTTPException(500, "Processing failed. Check the file and model configuration, then try again.") from exc
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "id": doc_id,
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
    mode: Literal[
        "conversational", "agent", "summary", "research", "extraction",
        "comparison", "factcheck", "coordinator", "invoice", "contract",
        "google_ai", "receipt", "resume", "compliance", "form_parser",
        "redaction", "classifier", "financial_statement", "translation", "anomaly_audit"
    ] = "conversational"
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

    # Deduct credits from user's company account
    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    mode_to_service = {"conversational": "chat", "agent": "research"}
    service_name = mode_to_service.get(payload.mode, payload.mode)
    cost = billing_service.get_service_cost(service_name)
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Company Free Trial credits depleted. Required: {cost}, Remaining: {account.remaining_credits} credits.",
        )
    billing_service.check_and_deduct_credits(
        account,
        service_name,
        document_id=doc_id,
        request_summary=payload.message[:80],
    )

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
            if not accumulated.getvalue():
                try:
                    billing_service.refund_credits(
                        account=account,
                        service_name=service_name,
                        credits_to_refund=cost,
                        document_id=doc_id,
                        reason="Chat stream failed before emitting content",
                    )
                except Exception:
                    pass
            yield "\n\n[STREAM ERROR] The model could not complete this response. If credits were deducted, they have been automatically refunded. Please try again."
        finally:
            # Persist the assistant turn once streaming is complete.
            text = accumulated.getvalue()
            execute(
                "INSERT INTO docuchat.messages (id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                (str(uuid.uuid4()), session_id, "assistant", text or "[no response]"),
            )

    return StreamingResponse(_event_stream(), media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Health & Service Status
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    """Health check endpoint: verifies DB, Redis, SeaweedFS, and Worker readiness for production probes."""
    db_status = "operational"
    try:
        query("SELECT 1", one=True)
    except Exception as exc:
        logging.warning("Health check DB query warning: %s", exc)
        db_status = "degraded"

    redis_ok = job_queue.is_healthy()
    storage_ok = storage_service.is_healthy()

    return {
        "status": "ok" if db_status == "operational" else "degraded",
        "database": db_status,
        "redis": "operational" if redis_ok else "fallback_in_memory",
        "storage": "operational" if storage_ok else "unavailable",
        "jobWorker": "active",
        "services": {
            s_id: "operational" for s_id in SERVICE_PRICING.keys()
        },
        "totalServices": len(SERVICE_PRICING),
        "version": "1.0.0",
    }


@app.get("/api/services/status")
def get_services_status():
    """Detailed operational status and tier metadata for all Document AI services."""
    return {
        "status": "ok",
        "services": billing_service.get_service_status(),
        "totalServices": len(SERVICE_PRICING),
    }


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
    doc = query(
        "SELECT id, filename, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(404, "Document not found")

    bundle = rag.get_bundle(doc_id)

    if bundle.pdf_docs:
        document = bundle.pdf_docs[0]
        content = document.get_page(page)
        if content is None:
            raise HTTPException(404, "Page or section not found")
        return {
            "page": page,
            "totalPages": document.total_pages,
            "text": content.text,
            "filename": document.name,
        }

    file_path = rag._pdf_path(doc_id)
    if not file_path.exists():
        text = rag.get_page_text(doc_id, page)
        if text is None:
            raise HTTPException(404, "Document file not found. Please re-upload the document.")
        return {
            "page": page,
            "totalPages": doc["page_count"] or 0,
            "text": text,
            "filename": doc["original_filename"],
        }

    from backend.documents.loader import load_document

    document = load_document(file_path)
    content = document.get_page(page)
    if content is None:
        raise HTTPException(404, "Page or section not found")
    return {"page": page, "totalPages": document.total_pages, "text": content.text, "filename": document.name}


@app.get("/api/documents/{doc_id}/ocr/blocks")
def get_document_ocr_blocks(
    doc_id: str,
    user: CurrentUser,
    page: Optional[int] = None,
    force_ocr: bool = False,
):
    """
    Extract and return layout-aware blocks (text, title, metadata, tables with content_md, images with descriptions).
    """
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(404, "Document not found")

    file_path = rag._pdf_path(doc_id)
    if not file_path.exists():
        candidates = [
            Path(f"backend/storage/uploads/{doc_id}.pdf"),
            Path(f"backend/storage/uploads/{doc_id}"),
            Path(f"/tmp/{doc_id}.pdf"),
            Path(f"/tmp/{doc['original_filename']}"),
        ]
        for c in candidates:
            if c.exists():
                file_path = c
                break

    if not file_path.exists():
        raise HTTPException(404, "Document file not found on storage.")

    from backend.agent.tools.ocr import OcrService

    ocr_service = OcrService()
    try:
        data = ocr_service.ocr_extract_blocks(file_path, page_number=page, force_ocr=force_ocr)
        return {
            "status": "success",
            "document_id": doc_id,
            "filename": doc["original_filename"],
            "total_pages": data.get("total_pages", doc["page_count"] or 1),
            "page": page,
            "ocr_text": data.get("ocr_text", ""),
            "coordinate_system": data.get("coordinate_system", "normalized_0_1000"),
            "blocks": data.get("blocks", []),
            "pages": data.get("pages", []),
        }
    except Exception as exc:
        logger.error("Failed to extract blocks for %s: %s", doc_id, exc)
        raise HTTPException(500, f"Block extraction failed: {exc}")


@app.get("/api/documents/{doc_id}/page/{page_num}/ocr/blocks")
def get_document_page_ocr_blocks(
    doc_id: str,
    page_num: int,
    user: CurrentUser,
    language: str = "auto",
    force_ocr: bool = False,
):
    """
    Extract bilingual Arabic and English layout blocks for a specific document page number.
    Returns blocks with reading direction, language classification, markdown tables, and visual descriptions.
    """
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(404, "Document not found")

    file_path = rag._pdf_path(doc_id)
    if not file_path.exists():
        candidates = [
            Path(f"backend/storage/uploads/{doc_id}.pdf"),
            Path(f"backend/storage/uploads/{doc_id}"),
            Path(f"/tmp/{doc_id}.pdf"),
            Path(f"/tmp/{doc['original_filename']}"),
        ]
        for c in candidates:
            if c.exists():
                file_path = c
                break

    if not file_path.exists():
        raise HTTPException(404, "Document file not found on storage.")

    from backend.agent.tools.ocr import OcrService

    ocr_service = OcrService()
    try:
        data = ocr_service.ocr_read_page_blocks(
            file_path,
            page_number=page_num,
            language=language,
            force_ocr=force_ocr,
        )
        return {
            "status": "success",
            "document_id": doc_id,
            "filename": doc["original_filename"],
            "page_number": page_num,
            "language_detected": data.get("language_detected", language),
            "direction": data.get("direction", "rtl" if language == "ar" else "ltr"),
            "block_count": data.get("block_count", len(data.get("blocks", []))),
            "ocr_text": data.get("ocr_text", ""),
            "coordinate_system": data.get("coordinate_system", "normalized_0_1000"),
            "blocks": data.get("blocks", []),
        }
    except Exception as exc:
        logger.error("Failed to extract page blocks for %s (page %d): %s", doc_id, page_num, exc)
        raise HTTPException(500, f"Page block extraction failed: {exc}")


# ---------------------------------------------------------------------------
# Document structure endpoint
# ---------------------------------------------------------------------------


@app.get("/api/documents/{doc_id}/outline")
def get_document_outline(doc_id: str, user: CurrentUser):
    """Return the structural outline (headings) of an uploaded document."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = rag._pdf_path(doc_id)

    from backend.documents.structure import extract_outline

    headings = []
    if file_path.exists():
        try:
            headings = extract_outline(file_path)
        except Exception:
            headings = []

    return {
        "documentId": str(doc["id"]),
        "filename": doc["original_filename"],
        "pageCount": doc["page_count"] or 0,
        "headings": [h.to_dict() for h in headings[:100]],
    }


# ---------------------------------------------------------------------------
# Agent capabilities endpoint
# ---------------------------------------------------------------------------


@app.get("/api/capabilities/agents")
def agent_capabilities(user: CurrentUser):
    """Return the available agent modes and their descriptions."""
    return {
        "modes": [
            {"value": "conversational", "name": "Document chat", "description": "Classic retrieval + LLM Q&A"},
            {"value": "agent", "name": "Research agent", "description": "General-purpose ReAct agent"},
            {"value": "summary", "name": "Summary agent", "description": "Executive summaries"},
            {"value": "research", "name": "Deep research", "description": "Evidence gathering + verification"},
            {"value": "extraction", "name": "Data extraction", "description": "Structured data extraction"},
            {"value": "comparison", "name": "Comparison", "description": "Multi-document comparison"},
            {"value": "factcheck", "name": "Fact-check", "description": "Claim verification"},
            {"value": "invoice", "name": "Invoice processing", "description": "Extract invoice data as JSON"},
            {"value": "contract", "name": "Contract analysis", "description": "Analyze contracts and flag risks"},
            {"value": "google_ai", "name": "Google AI Document", "description": "Google AI multimodal document intelligence, layout parsing, and entity extraction"},
            {"value": "receipt", "name": "Receipt & Expense", "description": "Extract merchant, items, taxes, tips, and totals as JSON"},
            {"value": "resume", "name": "Resume & Talent", "description": "Candidate skills, experience timeline, and qualification analysis"},
            {"value": "compliance", "name": "PII & Compliance", "description": "Detect sensitive PII, GDPR/HIPAA risks, and redaction guidance"},
            {"value": "form_parser", "name": "Form Parser", "description": "Extract key-value fields, checkboxes, and signature states"},
            {"value": "redaction", "name": "Bilingual Redaction", "description": "Mask Saudi National IDs, GCC IBANs, ZATCA Tax IDs, CR, and PII"},
            {"value": "classifier", "name": "Document Classifier", "description": "Classify document type (AR/EN), language, urgency, and department"},
            {"value": "financial_statement", "name": "Financial Statement", "description": "Extract P&L/Balance sheet metrics and financial ratios"},
            {"value": "translation", "name": "Bilingual Translation", "description": "Fidelity legal & financial translation between English and Arabic"},
            {"value": "anomaly_audit", "name": "Tax & Anomaly Audit", "description": "Verify ZATCA 15% VAT, subtotal math, and due dates"},
            {"value": "coordinator", "name": "Auto-routing", "description": "Routes to the best specialist"},
        ],
    }


# ---------------------------------------------------------------------------
# Multi-agent workflow endpoint
# ---------------------------------------------------------------------------


class WorkflowPayload(BaseModel):
    model: str | None = None
    responseStyle: Literal["concise", "balanced", "detailed"] = "balanced"


@app.post("/api/documents/{doc_id}/workflow")
def run_workflow(
    doc_id: str,
    payload: WorkflowPayload,
    user: CurrentUser,
):
    """Run a predefined workflow on a document — returns the full result."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    model = payload.model or settings.DEFAULT_MODEL
    if model not in settings.CHAT_MODELS:
        raise HTTPException(422, "Model is not enabled on this server.")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    # Deduct company credits
    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("coordinator")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "coordinator", document_id=doc_id, request_summary="Multi-agent workflow"
    )

    # Build a coordinator that routes to specialists
    coordinator = rag._build_agent(bundle, model, mode="coordinator")

    try:
        result = coordinator.run("Analyse this document comprehensively. Produce an executive summary, identify key data and metrics, highlight any comparisons or contradictions, and verify any claims you can find. Use all specialist agents as needed.")
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="coordinator",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Workflow execution did not complete successfully",
            )
            return {
                "documentId": str(doc["id"]),
                "title": doc["original_filename"],
                "result": result.response or "Workflow execution degraded or stopped.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Workflow failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="coordinator",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Workflow exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return {
        "documentId": str(doc["id"]),
        "title": doc["original_filename"],
        "result": result.response or "",
        "creditsDeducted": cost,
        "creditsRemaining": remaining,
        "success": result.success,
        "iterations": result.iterations,
        "steps": result.steps,
    }


# ---------------------------------------------------------------------------
# Google AI Document endpoint
# ---------------------------------------------------------------------------


class GoogleAIPayload(BaseModel):
    task: Literal["comprehensive", "entities", "layout", "tables"] = "comprehensive"
    model: str | None = None


@app.post("/api/documents/{doc_id}/google-ai")
def analyze_with_google_ai(
    doc_id: str,
    payload: GoogleAIPayload,
    user: CurrentUser,
):
    """Analyze a document using Google AI Document Intelligence."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    # Deduct company credits
    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("google_ai")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "google_ai", document_id=doc_id, request_summary=f"Google AI {payload.task} analysis"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="google_ai")

    try:
        result = agent.run(
            f"Perform a {payload.task} analysis on '{doc['original_filename']}' using Google AI document intelligence. Extract layout, entities, tables, and summarize."
        )
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="google_ai",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Google AI analysis did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "task": payload.task,
                "result": result.response or "Google AI service degraded or stopped.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Google AI analysis failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="google_ai",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Google AI exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google AI service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return {
        "documentId": str(doc["id"]),
        "filename": doc["original_filename"],
        "task": payload.task,
        "result": result.response or "",
        "creditsDeducted": cost,
        "creditsRemaining": remaining,
        "success": result.success,
        "iterations": result.iterations,
        "steps": result.steps,
    }


# ---------------------------------------------------------------------------
# Additional Document AI Service endpoints
# ---------------------------------------------------------------------------


class DocumentAIServicePayload(BaseModel):
    model: str | None = None


def _format_service_result(
    doc: dict,
    service_name: str,
    result: Any,
    bundle: Any,
    cost: int,
    remaining: int,
) -> dict:
    raw_text = getattr(result, "response", "") or ""
    parsed_json = _extract_json_from_text(raw_text)

    # Check agent steps for tool observations if not in final response
    if parsed_json is None and hasattr(result, "steps") and result.steps:
        for step in reversed(result.steps):
            obs = step.get("observation", "")
            if isinstance(obs, str) and ("{" in obs or "[" in obs):
                step_json = _extract_json_from_text(obs)
                if step_json:
                    parsed_json = step_json
                    break

    # If still not found, check if enhanced document toolkit has extractor tool
    if parsed_json is None and hasattr(bundle, "toolkit"):
        tk = bundle.toolkit
        filename = doc["original_filename"]
        try:
            if service_name == "invoice" and hasattr(tk, "extract_invoice_data"):
                tool_out = tk.extract_invoice_data(filename)
                parsed_json = _extract_json_from_text(tool_out)
            elif service_name == "contract" and hasattr(tk, "extract_contract_data"):
                tool_out = tk.extract_contract_data(filename)
                parsed_json = _extract_json_from_text(tool_out)
        except Exception as tk_err:
            logging.warning("Fallback extractor failed for %s: %s", service_name, tk_err)

    # Guarantee structured dictionary
    if parsed_json is None:
        parsed_json = extract_structured_data(raw_text, service=service_name)

    formatted_result = (
        json.dumps(parsed_json, indent=2, ensure_ascii=False)
        if isinstance(parsed_json, (dict, list))
        else raw_text
    )

    return {
        "documentId": str(doc["id"]),
        "filename": doc["original_filename"],
        "service": service_name,
        "result": formatted_result,
        "data": parsed_json,
        "creditsDeducted": cost,
        "creditsRemaining": remaining,
        "success": result.success,
        "iterations": result.iterations,
        "steps": result.steps,
    }


@app.post("/api/documents/{doc_id}/receipt")
def analyze_receipt(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Extract receipt, expense, and transaction intelligence as structured JSON."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("receipt")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "receipt", document_id=doc_id, request_summary="Receipt & expense extraction"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="receipt")
    try:
        result = agent.run(f"Extract all receipt and expense data from '{doc['original_filename']}'.")
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="receipt",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Receipt analysis did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": "receipt",
                "result": result.response or "Receipt service degraded or encountered errors.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Receipt analysis failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="receipt",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Receipt exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Receipt service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return _format_service_result(doc, "receipt", result, bundle, cost, remaining)


@app.post("/api/documents/{doc_id}/resume")
def analyze_resume(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Extract talent, skills, experience, and qualification profile from resumes/CVs."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("resume")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "resume", document_id=doc_id, request_summary="Resume & talent profiling"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="resume")
    try:
        result = agent.run(f"Extract candidate profile, skills taxonomy, and work history from '{doc['original_filename']}'.")
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="resume",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Resume analysis did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": "resume",
                "result": result.response or "Resume service degraded or encountered errors.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Resume analysis failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="resume",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Resume exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return _format_service_result(doc, "resume", result, bundle, cost, remaining)


@app.post("/api/documents/{doc_id}/compliance")
def audit_compliance(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Audit document for PII, GDPR/HIPAA compliance risks, and provide redaction advice."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("compliance")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "compliance", document_id=doc_id, request_summary="PII & compliance audit"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="compliance")
    try:
        result = agent.run(f"Audit '{doc['original_filename']}' for PII exposure, data privacy risks, and regulatory compliance.")
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="compliance",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Compliance audit did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": "compliance",
                "result": result.response or "Compliance service degraded or encountered errors.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Compliance audit failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="compliance",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Compliance exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return _format_service_result(doc, "compliance", result, bundle, cost, remaining)


@app.post("/api/documents/{doc_id}/form-parser")
def parse_form_fields(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Extract key-value fields, checkboxes, and signatures from structured forms."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("form_parser")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "form_parser", document_id=doc_id, request_summary="Form fields extraction"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="form_parser")
    try:
        result = agent.run(f"Parse all form fields, checkboxes, and signatures from '{doc['original_filename']}'.")
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="form_parser",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Form parser did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": "form_parser",
                "result": result.response or "Form parser service degraded or encountered errors.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Form parser failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="form_parser",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Form parser exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Form parser service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return _format_service_result(doc, "form_parser", result, bundle, cost, remaining)


@app.post("/api/documents/{doc_id}/comparison")
def analyze_comparison(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Compare content, clauses, and perspectives within and across documents."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("comparison")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "comparison", document_id=doc_id, request_summary="Document comparison"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="comparison")
    try:
        result = agent.run(f"Perform a comprehensive comparative analysis of key provisions and topics in '{doc['original_filename']}'.")
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="comparison",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Comparison did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": "comparison",
                "result": result.response or "Comparison service degraded or encountered errors.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Comparison analysis failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="comparison",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Comparison exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return {
        "documentId": str(doc["id"]),
        "filename": doc["original_filename"],
        "service": "comparison",
        "result": result.response or "",
        "creditsDeducted": cost,
        "creditsRemaining": remaining,
        "success": result.success,
        "iterations": result.iterations,
        "steps": result.steps,
    }


@app.post("/api/documents/{doc_id}/factcheck")
def analyze_factcheck(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Verify factual claims against document evidence and score validity."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("factcheck")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "factcheck", document_id=doc_id, request_summary="Fact-check verification"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="factcheck")
    try:
        result = agent.run(f"Identify and verify all factual claims, metrics, and dates in '{doc['original_filename']}'.")
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="factcheck",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Fact check did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": "factcheck",
                "result": result.response or "Fact-check service degraded or encountered errors.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Fact-check failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="factcheck",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Fact-check exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fact-check service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return {
        "documentId": str(doc["id"]),
        "filename": doc["original_filename"],
        "service": "factcheck",
        "result": result.response or "",
        "creditsDeducted": cost,
        "creditsRemaining": remaining,
        "success": result.success,
        "iterations": result.iterations,
        "steps": result.steps,
    }


@app.post("/api/documents/{doc_id}/invoice")
def analyze_invoice(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Extract invoice line items, tax, due date, and payment details."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("invoice")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "invoice", document_id=doc_id, request_summary="Invoice extraction"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="invoice")
    try:
        result = agent.run(
            f"Extract all invoice details, line items, taxes, vendor, and totals from '{doc['original_filename']}'. "
            "Return your final answer as clean, structured JSON only."
        )
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="invoice",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Invoice extraction did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": "invoice",
                "result": result.response or "Invoice service degraded or encountered errors.",
                "data": None,
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Invoice analysis failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="invoice",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Invoice exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invoice service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return _format_service_result(doc, "invoice", result, bundle, cost, remaining)


@app.post("/api/documents/{doc_id}/contract")
def analyze_contract(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Analyze contract terms, liabilities, indemnities, and termination clauses."""
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost("contract")
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, "contract", document_id=doc_id, request_summary="Contract analysis"
    )

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode="contract")
    try:
        result = agent.run(f"Analyze key clauses, termination, liabilities, and obligations in '{doc['original_filename']}'.")
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name="contract",
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or "Contract analysis did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": "contract",
                "result": result.response or "Contract service degraded or encountered errors.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Contract analysis failed: %s", exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name="contract",
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Contract exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contract service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return _format_service_result(doc, "contract", result, bundle, cost, remaining)


def _execute_specialized_service(
    service_name: str,
    doc_id: str,
    default_prompt: str,
    user: CurrentUser,
    model: str | None = None,
):
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s AND user_id = %s",
        (doc_id, str(user["id"])),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(doc_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload the document.")

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost(service_name)
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )
    remaining = billing_service.check_and_deduct_credits(
        account, service_name, document_id=doc_id, request_summary=f"Run {service_name}"
    )

    selected_model = model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, selected_model, mode=service_name)
    try:
        result = agent.run(default_prompt.format(filename=doc["original_filename"]))
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name=service_name,
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or f"{service_name} did not succeed",
            )
            return {
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "service": service_name,
                "result": result.response or f"{service_name} service degraded or encountered errors.",
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("%s failed: %s", service_name, exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name=service_name,
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"{service_name} exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{service_name} service error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    return _format_service_result(doc, service_name, result, bundle, cost, remaining)


@app.post("/api/documents/{doc_id}/redaction")
def redact_sensitive_pii(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Bilingual PII and tax data redaction (Saudi National ID, GCC IBAN, ZATCA Tax ID, CR, contacts)."""
    return _execute_specialized_service(
        service_name="redaction",
        doc_id=doc_id,
        default_prompt="Redact all sensitive PII, Saudi IDs, GCC IBANs, and ZATCA tax numbers from '{filename}'.",
        user=user,
        model=payload.model,
    )


@app.post("/api/documents/{doc_id}/classifier")
def classify_document_endpoint(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Classify document type, language (AR/EN), urgency, and routing department."""
    return _execute_specialized_service(
        service_name="classifier",
        doc_id=doc_id,
        default_prompt="Classify document '{filename}' and identify language, type, urgency, and routing.",
        user=user,
        model=payload.model,
    )


@app.post("/api/documents/{doc_id}/financial-statement")
def analyze_financial_statement_endpoint(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Analyze financial statements, balance sheet, income statement, and financial ratios."""
    return _execute_specialized_service(
        service_name="financial_statement",
        doc_id=doc_id,
        default_prompt="Extract and analyze financial metrics, ratios, and solvency indicators from '{filename}'.",
        user=user,
        model=payload.model,
    )


@app.post("/api/documents/{doc_id}/translation")
def translate_document_endpoint(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """High-fidelity bilingual translation between Arabic and English."""
    return _execute_specialized_service(
        service_name="translation",
        doc_id=doc_id,
        default_prompt="Translate document '{filename}' with high terminology fidelity between Arabic and English.",
        user=user,
        model=payload.model,
    )


@app.post("/api/documents/{doc_id}/anomaly-audit")
def audit_anomalies_endpoint(
    doc_id: str,
    payload: DocumentAIServicePayload,
    user: CurrentUser,
):
    """Audit invoice calculations, ZATCA 15% VAT, and chronological date integrity."""
    return _execute_specialized_service(
        service_name="anomaly_audit",
        doc_id=doc_id,
        default_prompt="Perform mathematical anomaly and ZATCA 15% tax compliance audit on '{filename}'.",
        user=user,
        model=payload.model,
    )


# ---------------------------------------------------------------------------
# Company Billing, API Keys, and Enterprise Quota Endpoints
# ---------------------------------------------------------------------------


async def get_company_account(
    user: CurrentUser,
) -> CompanyAccount:
    """Dependency for authenticated web users to get or create their company trial."""
    return billing_service.get_or_create_company(user["id"], user.get("name"))


async def get_company_or_api_auth(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> CompanyAccount:
    """Authenticates either via X-API-Key header or Bearer JWT token."""
    # 1. API key in custom header
    if x_api_key:
        account = billing_service.get_company_by_api_key(x_api_key)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive company API key.",
            )
        return account

    # 2. API key passed as Bearer token
    if authorization and authorization.startswith("Bearer docu_live_"):
        key = authorization[len("Bearer "):].strip()
        account = billing_service.get_company_by_api_key(key)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive company API key.",
            )
        return account

    # 3. Standard JWT auth
    from backend.auth import get_current_user

    user = await get_current_user(authorization)
    return billing_service.get_or_create_company(user["id"], user.get("name"))


CompanyAuth = Annotated[CompanyAccount, Depends(get_company_or_api_auth)]


@app.get("/api/company/account")
def get_company_status(
    account: CompanyAccount = Depends(get_company_account),
):
    """Retrieve company account status, remaining credits, and masked API key."""
    return {
        "id": account.id,
        "companyName": account.company_name,
        "planTier": account.plan_tier,
        "isFreeTrialOnly": True,
        "totalCredits": account.total_credits,
        "usedCredits": account.used_credits,
        "remainingCredits": account.remaining_credits,
        "apiKeyPrefix": account.api_key_prefix,
        "apiKey": f"{account.api_key[:14]}••••••••••••••••••••••••{account.api_key[-4:]}",
        "rawApiKey": account.api_key,
        "createdAt": account.created_at,
    }


@app.post("/api/company/api-key/regenerate")
def roll_api_key(
    user: CurrentUser,
):
    """Regenerate company API key and return unmasked key."""
    new_acc = billing_service.regenerate_api_key(user["id"])
    return {
        "apiKey": new_acc.api_key,
        "apiKeyPrefix": new_acc.api_key_prefix,
        "remainingCredits": new_acc.remaining_credits,
        "planTier": new_acc.plan_tier,
    }


@app.get("/api/company/pricing")
def get_pricing_catalog():
    """Return the credit cost per service based on LLM compute usage."""
    return {
        "plan": "Company Free Trial",
        "initialCredits": INITIAL_TRIAL_CREDITS,
        "freeTrialAvailableOnly": True,
        "services": [
            {
                "id": s_id,
                "name": info["name"],
                "credits": info["credits"],
                "llmTier": info["llm_tier"],
                "category": info["category"],
                "description": info["description"],
            }
            for s_id, info in SERVICE_PRICING.items()
        ],
    }


@app.get("/api/company/usage")
def get_company_usage_history(
    account: CompanyAccount = Depends(get_company_account),
):
    """Retrieve audit usage history of Document AI calls."""
    logs = billing_service.get_usage_logs(account.id, limit=100)
    return {
        "companyId": account.id,
        "totalCredits": account.total_credits,
        "usedCredits": account.used_credits,
        "remainingCredits": account.remaining_credits,
        "logs": logs,
    }


# ---------------------------------------------------------------------------
# Public Company Document AI API (/api/v1/services/{service_name})
# ---------------------------------------------------------------------------


class CompanyExecutionPayload(BaseModel):
    document_id: str
    query: str | None = None
    model: str | None = None


@app.post("/api/v1/services/{service_name}")
def execute_company_service(
    service_name: str,
    payload: CompanyExecutionPayload,
    response: Response,
    account: CompanyAuth,
):
    """Execute a Document AI service using company API key with atomic credit deduction."""
    normalized_service = service_name.lower().replace("-", "_")

    if normalized_service not in SERVICE_PRICING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown service '{service_name}'. Valid services: {', '.join(SERVICE_PRICING.keys())}",
        )

    cost = billing_service.get_service_cost(normalized_service)

    # 1. Verify credit balance before execution
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Insufficient credits for '{normalized_service}'. Required: {cost}, "
                f"Remaining: {account.remaining_credits}. Company Free Trial credits depleted."
            ),
        )

    # 2. Check document
    doc = query(
        "SELECT id, original_filename, page_count FROM docuchat.documents WHERE id = %s",
        (payload.document_id,),
        one=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    bundle = rag.get_bundle(payload.document_id)
    if bundle.vector_store is None:
        raise HTTPException(500, "Document index not available. Re-upload or process the document.")

    # 3. Deduct credits atomically
    try:
        remaining = billing_service.check_and_deduct_credits(
            account=account,
            service_name=normalized_service,
            document_id=payload.document_id,
            request_summary=payload.query or f"API execution of {normalized_service}",
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))

    # 4. Execute the Document AI Agent with fault tolerance and automatic refund on down/error
    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode=normalized_service)

    task_prompt = payload.query or f"Perform full {normalized_service} intelligence extraction on '{doc['original_filename']}'."

    try:
        result = agent.run(task_prompt)
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name=normalized_service,
                credits_to_refund=cost,
                document_id=payload.document_id,
                reason=result.error or f"{normalized_service} execution did not complete successfully",
            )
            response.headers["X-Credits-Cost"] = "0"
            response.headers["X-Credits-Remaining"] = str(remaining)
            response.headers["X-Credits-Refunded"] = str(cost)
            response.headers["X-Trial-Plan"] = "free_trial"
            return {
                "status": "failed",
                "service": normalized_service,
                "documentId": str(doc["id"]),
                "filename": doc["original_filename"],
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "planTier": account.plan_tier,
                "result": result.response or "The service encountered an error and could not complete.",
                "success": False,
                "error": result.error,
                "iterations": result.iterations,
                "steps": result.steps,
            }
    except Exception as exc:
        logging.exception("Agent execution exception in %s: %s", normalized_service, exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name=normalized_service,
            credits_to_refund=cost,
            document_id=payload.document_id,
            reason=f"Service exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service '{normalized_service}' failed: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    # Set response headers
    response.headers["X-Credits-Cost"] = str(cost)
    response.headers["X-Credits-Remaining"] = str(remaining)
    response.headers["X-Trial-Plan"] = "free_trial"

    return {
        "status": "success",
        "service": normalized_service,
        "documentId": str(doc["id"]),
        "filename": doc["original_filename"],
        "creditsDeducted": cost,
        "creditsRemaining": remaining,
        "planTier": account.plan_tier,
        "result": result.response or "",
        "success": result.success,
        "iterations": result.iterations,
        "steps": result.steps,
    }


class PlaygroundRunPayload(BaseModel):
    service: str = Field(..., description="Target service: invoice, contract, receipt, etc.")
    document_id: Optional[str] = Field(None, description="Existing document ID from drive/workspace")
    text_content: Optional[str] = Field(None, description="Raw text or sample document text for testing")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt override")
    user_prompt: Optional[str] = Field(None, description="Custom task / user query prompt")
    schema_override: Optional[Any] = Field(None, description="Target JSON schema or template structure")
    model: Optional[str] = Field(None, description="Model override (e.g. gpt-4o, gpt-4o-mini)")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    output_format: Literal["json", "markdown", "auto"] = Field("auto", description="Desired output format")


PlaygroundRunPayload.model_rebuild()


@app.get("/api/playground/presets")
def get_playground_presets(user: CurrentUser):
    """Retrieve service presets, default prompts, schemas, and sample contexts for the playground."""
    from backend.agent.playground_presets import SERVICE_PRESETS
    model_list = list(dict.fromkeys(
        ([settings.DEFAULT_MODEL] if settings.DEFAULT_MODEL else []) +
        (settings.CHAT_MODELS if settings.CHAT_MODELS else [])
    ))
    if not model_list:
        model_list = [settings.DEFAULT_MODEL]
    models = [{"id": m, "name": m, "description": f"Model configured in .env ({m})"} for m in model_list]
    # Sanitize presets to hide internal system prompts from clients
    sanitized_presets = {}
    for key, data in SERVICE_PRESETS.items():
        preset_copy = dict(data)
        preset_copy.pop("default_system_prompt", None)
        sanitized_presets[key] = preset_copy
    return {
        "presets": sanitized_presets,
        "models": models,
        "defaultModel": settings.DEFAULT_MODEL,
    }


@app.post("/api/playground/run")
def run_playground(
    payload: PlaygroundRunPayload,
    user: CurrentUser,
):
    """
    Execute an interactive playground run for any Document AI service.
    Supports comparing models/prompts, custom schemas, raw text / sample docs, or drive documents.
    """
    from backend.agent.playground_presets import SERVICE_PRESETS

    service_name = payload.service.lower().replace("-", "_")
    if service_name not in SERVICE_PRICING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown service '{payload.service}'. Supported: {', '.join(SERVICE_PRICING.keys())}",
        )

    account = billing_service.get_or_create_company(user["id"], user.get("name"))
    cost = billing_service.get_service_cost(service_name)
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient company credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )

    # Resolve document context
    filename = "playground_sample.txt"
    doc_id = payload.document_id
    bundle = None

    if doc_id:
        doc = query(
            "SELECT id, original_filename FROM docuchat.documents WHERE id = %s AND user_id = %s",
            (doc_id, str(user["id"])),
            one=True,
        )
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        filename = doc["original_filename"]
        bundle = rag.get_bundle(doc_id)
    elif payload.text_content and payload.text_content.strip():
        bundle = rag.create_text_bundle(payload.text_content.strip(), name=f"{service_name}_sample.txt")
        filename = f"{service_name}_sample.txt"
        doc_id = bundle.doc_id
    else:
        preset = SERVICE_PRESETS.get(service_name)
        if preset and preset.get("sample_text"):
            sample = preset["sample_text"]
            bundle = rag.create_text_bundle(sample, name=f"{service_name}_preset_sample.txt")
            filename = f"{service_name}_preset_sample.txt"
            doc_id = bundle.doc_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either document_id or text_content must be provided.",
            )

    if bundle.vector_store is None:
        raise HTTPException(status_code=500, detail="Document vector store failed to initialize.")

    remaining = billing_service.check_and_deduct_credits(
        account, service_name, document_id=doc_id, request_summary=f"Playground run: {service_name}"
    )

    preset = SERVICE_PRESETS.get(service_name, {})
    effective_system_prompt = payload.system_prompt or preset.get("default_system_prompt")

    schema_instruction = ""
    if payload.schema_override:
        schema_dump = (
            json.dumps(payload.schema_override, indent=2, ensure_ascii=False)
            if isinstance(payload.schema_override, (dict, list))
            else str(payload.schema_override)
        )
        schema_instruction = (
            f"\n\nOUTPUT SCHEMA REQUIREMENT:\n"
            f"You MUST format and return your final response strictly as a JSON object adhering to this schema/structure:\n"
            f"```json\n{schema_dump}\n```\n"
            f"Return ONLY valid JSON matching this schema."
        )

    if effective_system_prompt and schema_instruction:
        effective_system_prompt = effective_system_prompt + schema_instruction

    task_prompt = (
        payload.user_prompt
        or preset.get("default_query")
        or f"Perform complete {service_name} intelligence analysis on '{filename}'."
    )
    if not effective_system_prompt and schema_instruction:
        task_prompt = task_prompt + schema_instruction

    model = payload.model or settings.DEFAULT_MODEL
    temp = payload.temperature

    agent = rag._build_agent(
        bundle=bundle,
        model_name=model,
        mode=service_name,
        system_prompt=effective_system_prompt,
        temperature=temp,
    )

    t0 = time.time()
    try:
        result = agent.run(task_prompt)
        latency_ms = int((time.time() - t0) * 1000)

        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name=service_name,
                credits_to_refund=cost,
                document_id=doc_id,
                reason=result.error or f"Playground {service_name} execution failed",
            )
            return {
                "success": False,
                "service": service_name,
                "model": model,
                "documentId": doc_id,
                "filename": filename,
                "latencyMs": latency_ms,
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "error": result.error,
                "result": result.response or "",
                "data": None,
                "iterations": result.iterations,
                "steps": result.steps,
            }

        raw_text = getattr(result, "response", "") or ""
        parsed_json = _extract_json_from_text(raw_text)

        if parsed_json is None and hasattr(result, "steps") and result.steps:
            for step in reversed(result.steps):
                obs = step.get("observation", "")
                if isinstance(obs, str) and ("{" in obs or "[" in obs):
                    step_json = _extract_json_from_text(obs)
                    if step_json:
                        parsed_json = step_json
                        break

        is_structured_svc = service_name in [
            "invoice", "receipt", "contract", "compliance", "form_parser",
            "resume", "redaction", "classifier", "financial_statement", "translation", "anomaly_audit"
        ]
        if (payload.output_format == "json" or payload.schema_override or is_structured_svc) and parsed_json is None:
            parsed_json = extract_structured_data(raw_text, service=service_name)

        formatted_result = (
            json.dumps(parsed_json, indent=2, ensure_ascii=False)
            if isinstance(parsed_json, (dict, list))
            else raw_text
        )

        return {
            "success": True,
            "service": service_name,
            "model": model,
            "temperature": temp,
            "documentId": doc_id,
            "filename": filename,
            "latencyMs": latency_ms,
            "creditsDeducted": cost,
            "creditsRemaining": remaining,
            "result": formatted_result,
            "data": parsed_json,
            "raw": raw_text,
            "iterations": result.iterations,
            "steps": result.steps,
            "schemaUsed": payload.schema_override,
            "promptUsed": task_prompt,
        }

    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        logging.exception("Playground run failed for %s: %s", service_name, exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name=service_name,
            credits_to_refund=cost,
            document_id=doc_id,
            reason=f"Playground exception: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Playground execution failed: {exc}. Credits refunded (Remaining: {remaining}).",
        )

