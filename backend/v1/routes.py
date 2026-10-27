"""
B2B SaaS Pipeline & Developer API Router (v1).

Provides enterprise-ready endpoints for data pipelines (Airflow, Celery,
ETL scripts, CI/CD) and AI agent integrations (Claude, ChatGPT, OpenAI tool calling).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend import rag
from backend.billing import (
    INITIAL_TRIAL_CREDITS,
    SERVICE_PRICING,
    CompanyAccount,
    InsufficientCreditsError,
    billing_service,
)
from backend.config import settings
from backend.db import query
from backend.documents.loader import SUPPORTED_EXTENSIONS
from backend.documents.limits import (
    MAX_UPLOAD_BYTES, UploadSizeError, validate_pdf_pages, validate_upload_size,
)
from backend.jobs import job_queue
from backend.storage import storage_service
from backend.storage.ephemeral import ephemeral_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["B2B SaaS Pipeline API"])


# ---------------------------------------------------------------------------
# Authentication Dependency
# ---------------------------------------------------------------------------


async def get_company_or_api_auth(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key: Optional[str] = Query(None),
) -> CompanyAccount:
    """Authenticates via X-API-Key header, Bearer API key, query param, or JWT."""
    # 1. Check direct API key
    key = x_api_key or api_key
    if not key and authorization and authorization.startswith("Bearer docu_live_"):
        key = authorization[len("Bearer ") :].strip()

    if key:
        account = billing_service.get_company_by_api_key(key)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive company API key.",
            )
        return account

    # 2. Check JWT bearer token
    from backend.auth import get_current_user

    try:
        user = await get_current_user(authorization)
        return billing_service.get_or_create_company(user["id"], user.get("name"))
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide 'X-API-Key' header with your company key (docu_live_...).",
        )


CompanyAuth = Depends(get_company_or_api_auth)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RawUploadPayload(BaseModel):
    content: str = Field(..., description="Raw text or markdown content of document")
    filename: str = Field("document.txt", description="Filename including extension")


class PipelineRunPayload(BaseModel):
    document_id: Optional[str] = Field(None, description="Target document ID from POST /api/v1/documents/upload")
    text_content: Optional[str] = Field(None, description="Direct text to process if not passing document_id")
    service: str = Field(
        "summary",
        description="Service: invoice, contract, compliance, summary, form_parser, receipt, resume, research, chat",
    )
    query: Optional[str] = Field(None, description="Optional custom prompt or question")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt override")
    schema_override: Optional[Any] = Field(None, description="Optional target JSON schema / structure")
    output_format: Literal["json", "markdown", "auto"] = Field(
        "auto", description="Desired format: structured json, markdown, or auto"
    )
    model: Optional[str] = Field(None, description="Optional LLM model override")
    webhook_url: Optional[str] = Field(
        None, description="Optional webhook URL to receive async task completion callback"
    )


class BatchTaskPayload(BaseModel):
    document_id: str
    service: str
    query: Optional[str] = None
    output_format: Literal["json", "markdown", "auto"] = "auto"


class PipelineBatchPayload(BaseModel):
    tasks: List[BatchTaskPayload]
    webhook_url: Optional[str] = None


class OcrBlocksPayload(BaseModel):
    document_id: str = Field(..., description="Target document ID")
    page: Optional[int] = Field(None, description="Optional 1-indexed page number")
    language: str = Field("auto", description="Language mode: 'auto', 'ar' (Arabic), 'en' (English), or 'mixed'")
    force_ocr: bool = Field(False, description="Force vision-based OCR re-extraction")


class OcrPageBlocksPayload(BaseModel):
    document_id: str = Field(..., description="Target document ID")
    page_number: int = Field(1, description="1-indexed page number")
    language: str = Field("auto", description="Language mode: 'auto', 'ar', 'en', or 'mixed'")
    force_ocr: bool = Field(False, description="Force vision-based OCR re-extraction")


class AdvancedOcrPayload(BaseModel):
    document_id: str = Field(..., min_length=1, description="Uploaded PDF document ID")
    start_page: int = Field(1, ge=1)
    end_page: Optional[int] = Field(None, ge=1, description="Inclusive; defaults to the last page")
    language: Literal["auto", "ar", "en", "mixed"] = "auto"


# ---------------------------------------------------------------------------
# Webhook Helper
# ---------------------------------------------------------------------------


async def _dispatch_webhook(url: str, payload: Dict[str, Any], secret: Optional[str] = None) -> None:
    """Send cryptographically signed HMAC-SHA256 webhook notification for enterprise pipelines."""
    try:
        raw_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        timestamp = str(int(time.time()))
        signing_secret = secret or settings.JWT_SECRET
        signature = hmac.new(
            signing_secret.encode("utf-8"),
            f"{timestamp}.".encode("utf-8") + raw_body,
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-DOCTool-Timestamp": timestamp,
            "X-DOCTool-Signature": f"sha256={signature}",
            "X-DocuChat-Timestamp": timestamp,
            "X-DocuChat-Signature": f"sha256={signature}",
            "User-Agent": "DOCTool-Enterprise-Webhook/1.0",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=raw_body, headers=headers)
            logger.info("Dispatched signed webhook to %s, status=%d", url, resp.status_code)
    except Exception as exc:
        logger.warning("Failed to dispatch webhook to %s: %s", url, exc)


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any] | List[Any]]:
    """Extract embedded JSON blocks or valid JSON from agent response."""
    if not text:
        return None
    text = text.strip()
    # 1. Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. Try fenced code blocks ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    # 3. Try balanced braces search
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if c == '"' and not escape:
                in_string = not in_string
            elif not in_string:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : i + 1]
                        try:
                            res = json.loads(candidate)
                            if isinstance(res, (dict, list)):
                                return res
                        except Exception:
                            pass
                        break
            escape = (c == "\\" and not escape)
        start = text.find("{", start + 1)

    # 4. Try greedy curly brackets fallback
    curly = re.search(r"(\{[\s\S]*\})", text)
    if curly:
        try:
            return json.loads(curly.group(1))
        except Exception:
            pass

    return None


def extract_structured_data(text: str, service: str = "general") -> Dict[str, Any]:
    """Extract structured dictionary from text, falling back to parsed key-value lines."""
    parsed = _extract_json_from_text(text)
    if isinstance(parsed, dict) and parsed:
        return parsed
    if isinstance(parsed, list):
        return {"items": parsed, "count": len(parsed)}

    # Parse prose bullet points or key-value lines
    data: Dict[str, Any] = {}
    current_key = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("```") or line.startswith("==="):
            continue
        clean = re.sub(r"^[-*•#\d\.\s]+", "", line).strip()
        if ":" in clean:
            k, v = clean.split(":", 1)
            k = re.sub(r"[*_#]", "", k).strip().lower().replace(" ", "_").replace("-", "_")
            v = re.sub(r"^\*\*|\*\*$", "", v).strip()
            if k and v:
                data[k] = v
                current_key = k
        elif current_key and clean:
            if isinstance(data[current_key], str):
                data[current_key] += " " + clean
    if data:
        return data

    return {"summary": text.strip() if text else "No content extracted", "service": service}


# ---------------------------------------------------------------------------
# Pipeline Routes
# ---------------------------------------------------------------------------


@router.post("/documents/upload", summary="Pipeline Document Ingestion")
async def pipeline_upload_document(
    request: Request,
    account: CompanyAccount = CompanyAuth,
):
    """
    Ingest and index a document into the B2B pipeline.
    Accepts multipart file or raw JSON content payload.
    Returns document ID and indexing metrics immediately for subsequent pipeline steps.
    """
    content_type = request.headers.get("content-type", "")
    filename = "document.txt"
    mime_type = "text/plain"
    raw_bytes = b""
    ttl_minutes: Optional[int] = None

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "Invalid JSON payload.")
        text_content = body.get("content", "")
        if not text_content:
            raise HTTPException(400, "Field 'content' is required in JSON payload.")
        filename = body.get("filename", "document.txt")
        raw_bytes = text_content.encode("utf-8")
        mime_type = "text/plain"
        if body.get("ttl_minutes"):
            try:
                ttl_minutes = int(body["ttl_minutes"])
            except (ValueError, TypeError):
                pass
    elif "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if not uploaded_file or not hasattr(uploaded_file, "filename"):
            raise HTTPException(400, "Multipart file 'file' field is required.")
        filename = Path((uploaded_file.filename or "").replace("\\", "/")).name
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format '{ext}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
            )
        raw_bytes = await uploaded_file.read(MAX_UPLOAD_BYTES + 1)
        if not raw_bytes or len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Document size must be between 1 byte and 5 MB.")
        mime_type = uploaded_file.content_type or "application/octet-stream"
        raw_ttl = form.get("ttl_minutes")
        if raw_ttl:
            try:
                ttl_minutes = int(raw_ttl)
            except (ValueError, TypeError):
                pass
    else:
        # Raw bytes stream
        raw_bytes = await request.body()
        if not raw_bytes:
            raise HTTPException(400, "Empty upload payload.")
        filename = request.headers.get("X-Filename", "document.txt")
        mime_type = content_type or "application/octet-stream"

    try:
        validate_upload_size(len(raw_bytes))
    except UploadSizeError as exc:
        raise HTTPException(413, str(exc)) from exc

    file_size = len(raw_bytes)
    ext = Path(filename).suffix.lower() or ".txt"

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(raw_bytes)
        tmp_path = tmp.name

    try:
        upload_result = await run_in_threadpool(
            rag.process_upload,
            user_id=str(account.user_id),
            file_path=Path(tmp_path),
            original_filename=filename,
            file_size=file_size,
            mime=mime_type,
        )
        chunk_count = upload_result[0]
        page_count = upload_result[1]
        doc_id = getattr(upload_result, "document_id", None) or str(uuid.uuid4())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Pipeline document processing failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline ingestion failed: {exc}",
        )
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass

    # Register in Ephemeral Store with configurable inactivity TTL
    dest_path = Path(settings.UPLOAD_DIR) / doc_id / filename
    if not dest_path.exists():
        e_doc = ephemeral_store.store_bytes(
            raw_bytes=raw_bytes,
            filename=filename,
            user_id=str(account.user_id),
            mime_type=mime_type,
            ttl_minutes=ttl_minutes,
            doc_id=doc_id,
        )
    else:
        e_doc = ephemeral_store.register_file(
            doc_id=doc_id,
            user_id=str(account.user_id),
            file_path=dest_path,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            page_count=page_count,
            chunk_count=chunk_count,
            ttl_minutes=ttl_minutes,
        )

    return {
        "status": "success",
        "documentId": doc_id,
        "filename": filename,
        "fileSize": file_size,
        "pageCount": page_count,
        "chunkCount": chunk_count,
        "ttlMinutes": e_doc.ttl_minutes,
        "remainingSeconds": e_doc.remaining_seconds,
        "expiresAt": e_doc.expires_at.isoformat(),
        "creditsRemaining": account.remaining_credits,
        "message": f"Document session active. Retained for {e_doc.ttl_minutes} minutes without usage. Inactivity resets on each service call.",
    }


@router.get("/documents", summary="List Company Pipeline Documents")
def pipeline_list_documents(
    account: CompanyAccount = CompanyAuth,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List documents indexed for the company account."""
    try:
        rows = (
            query(
                "SELECT id, filename, original_filename, file_size, mime_type, page_count, created_at "
                "FROM docuchat.documents WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (account.user_id, limit, offset),
            )
            or []
        )
    except Exception:
        # Fallback to in-memory registry if DB query fails
        rows = []

    return {
        "companyId": account.id,
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "documents": [
            {
                "id": str(r["id"]),
                "filename": r["original_filename"],
                "fileSize": r["file_size"],
                "pageCount": r["page_count"],
                "mimeType": r["mime_type"],
                "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/documents/{doc_id}", summary="Get Pipeline Document Details")
def pipeline_get_document(
    doc_id: str,
    account: CompanyAccount = CompanyAuth,
):
    """Retrieve document status, page count, and indexing bundle."""
    try:
        row = query(
            "SELECT id, original_filename, file_size, mime_type, page_count, created_at "
            "FROM docuchat.documents WHERE id = %s",
            (doc_id,),
            one=True,
        )
    except Exception:
        row = None

    if not row:
        # Check if bundle is loaded in-memory
        bundle = rag._registry.get(doc_id)
        if not bundle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{doc_id}' not found.",
            )
        return {
            "id": doc_id,
            "filename": f"doc_{doc_id}.pdf",
            "pageCount": len(bundle.pdf_docs[0].pages) if bundle.pdf_docs else 1,
            "isReady": bundle.vector_store is not None,
        }

    return {
        "id": str(row["id"]),
        "filename": row["original_filename"],
        "fileSize": row["file_size"],
        "mimeType": row["mime_type"],
        "pageCount": row["page_count"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "isReady": True,
    }


@router.get("/documents/{doc_id}/status", summary="Check Ephemeral Document Inactivity TTL Status")
def pipeline_get_document_status(
    doc_id: str,
    account: CompanyAccount = CompanyAuth,
):
    """Check remaining seconds and expiration for an active document session."""
    e_doc = ephemeral_store.get_and_touch(doc_id, extend_ttl=False)
    if not e_doc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Document session '{doc_id}' has expired after {settings.DOC_TTL_MINUTES} minutes of inactivity or does not exist.",
        )
    return {
        "status": "active",
        **e_doc.to_dict(),
    }


@router.delete("/documents/{doc_id}", summary="Delete Ephemeral Document Session")
def pipeline_delete_document(
    doc_id: str,
    account: CompanyAccount = CompanyAuth,
):
    """Purge document session and delete all associated files immediately."""
    deleted = ephemeral_store.delete(doc_id)
    return {
        "status": "success" if deleted else "not_found",
        "documentId": doc_id,
        "message": "Document session and storage purged." if deleted else "Document session not found or already purged.",
    }


@router.get("/documents/{doc_id}/search", summary="Pipeline Hybrid Chunk Retrieval")
def pipeline_search_document(
    doc_id: str,
    query_text: str = Query(..., alias="query", description="Search query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of chunks to return"),
    account: CompanyAccount = CompanyAuth,
):
    """
    Search document chunks using hybrid semantic embeddings + BM25 keyword search.
    Provides page citations and content for external RAG pipelines.
    """
    try:
        bundle = rag.get_bundle(doc_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to load document '{doc_id}': {exc}",
        )

    if bundle.vector_store is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document vector store is not indexed.",
        )

    docs = bundle.vector_store.search(query_text, top_k=top_k)
    results = []
    for d in docs:
        results.append(
            {
                "page": d.metadata.get("start_page") or d.metadata.get("page") or 1,
                "chunkIndex": d.metadata.get("chunk_index"),
                "source": d.metadata.get("source"),
                "content": d.page_content,
            }
        )

    return {
        "documentId": doc_id,
        "query": query_text,
        "count": len(results),
        "results": results,
    }


def _resolve_document_file_path(doc_id: str) -> tuple[Path, str]:
    """Helper to locate document on disk or storage and touch sliding inactivity TTL."""
    e_doc = ephemeral_store.get_and_touch(doc_id, extend_ttl=True)
    if e_doc and e_doc.file_path and e_doc.file_path.exists():
        return e_doc.file_path, e_doc.filename

    filename = f"doc_{doc_id}.pdf"
    file_path = None
    try:
        row = query(
            "SELECT original_filename, file_path FROM docuchat.documents WHERE id = %s",
            (doc_id,),
            one=True,
        )
        if row:
            filename = row["original_filename"]
            if row.get("file_path") and Path(row["file_path"]).exists():
                file_path = Path(row["file_path"])
    except Exception:
        pass

    if not file_path:
        for p in [
            rag._pdf_path(doc_id),
            Path(f"backend/storage/uploads/{doc_id}.pdf"),
            Path(f"backend/storage/uploads/{doc_id}"),
            Path(f"/tmp/{doc_id}.pdf"),
            Path(f"/tmp/{filename}"),
        ]:
            if p and p.exists():
                file_path = p
                break

    if not file_path:
        bundle = rag._registry.get(doc_id)
        if bundle and getattr(bundle, "pdf_docs", None) and bundle.pdf_docs:
            pdf_doc = bundle.pdf_docs[0]
            if getattr(pdf_doc, "file_path", None) and Path(pdf_doc.file_path).exists():
                file_path = Path(pdf_doc.file_path)

    if not file_path or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file for ID '{doc_id}' not found on storage.",
        )
    return file_path, filename


@router.post("/ocr/advanced", summary="Advanced OCR: Flexible Semantic Page Blocks", tags=["Advanced OCR"])
async def pipeline_advanced_ocr(
    request: Request,
    account: CompanyAccount = CompanyAuth,
):
    """Extract semantic blocks from an uploaded PDF or active ephemeral document session.

    Stateless ephemeral Document AI: documents are retained for 10 minutes without usage.
    Each usage resets the 10-minute inactivity timer. After 10 minutes of inactivity,
    files and resources are automatically purged.
    Documents are limited to 5 MB and 3 pages, including when selecting a page range. The first selected page has no predecessor context.
    """
    from backend.agent.tools.advanced_ocr import AdvancedOcrService
    from backend.agent.tools.ocr import OcrError

    content_type = request.headers.get("content-type", "")
    target_path: Optional[Path] = None
    target_filename: str = "document.pdf"
    target_doc_id: Optional[str] = None
    e_doc: Optional[EphemeralDocument] = None
    tmp_path_to_clean: Optional[Path] = None

    start_page: int = 1
    end_page: Optional[int] = None
    language: str = "auto"

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON payload.")
        doc_id = body.get("document_id")
        if not doc_id:
            raise HTTPException(status_code=422, detail="Field 'document_id' or 'file' is required.")
        e_doc = ephemeral_store.get_and_touch(str(doc_id), extend_ttl=True)
        if not e_doc:
            raise HTTPException(
                status_code=422,
                detail=f"Document session '{doc_id}' not found or expired after inactivity.",
            )
        target_path = e_doc.file_path
        target_filename = e_doc.filename
        target_doc_id = e_doc.doc_id

        raw_start = body.get("start_page", 1)
        try:
            start_page = int(raw_start)
            if start_page < 1:
                raise ValueError("start_page must be >= 1")
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="start_page must be an integer >= 1")

        raw_end = body.get("end_page")
        if raw_end is not None and str(raw_end).strip() != "":
            try:
                end_page = int(raw_end)
                if end_page < start_page:
                    raise ValueError("end_page must be >= start_page")
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="end_page must be an integer >= start_page")

        language = str(body.get("language", "auto")).lower()

    elif "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        form_doc_id = form.get("document_id")

        if not uploaded_file and not form_doc_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A PDF document 'file' or active 'document_id' is required.",
            )

        if form_doc_id and not uploaded_file:
            e_doc = ephemeral_store.get_and_touch(str(form_doc_id), extend_ttl=True)
            if not e_doc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Document session '{form_doc_id}' not found or expired after inactivity.",
                )
            target_path = e_doc.file_path
            target_filename = e_doc.filename
            target_doc_id = e_doc.doc_id
        elif uploaded_file:
            if not hasattr(uploaded_file, "filename"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A valid PDF document 'file' is required.",
                )
            raw_filename = Path((uploaded_file.filename or "document.pdf").replace("\\", "/")).name
            if Path(raw_filename).suffix.lower() != ".pdf":
                raise HTTPException(status_code=422, detail="Advanced OCR requires a PDF document")

            raw_bytes = await uploaded_file.read(MAX_UPLOAD_BYTES + 1)
            if not raw_bytes or len(raw_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="PDF size must be between 1 byte and 5 MB.")

            try:
                validate_pdf_pages(raw_bytes)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc

            # Store in ephemeral store with sliding inactivity TTL (default 10 min)
            try:
                e_doc = ephemeral_store.store_bytes(
                    raw_bytes=raw_bytes,
                    filename=raw_filename,
                    user_id=str(account.user_id),
                    mime_type="application/pdf",
                )
                target_path = e_doc.file_path
                target_filename = e_doc.filename
                target_doc_id = e_doc.doc_id
            except Exception:
                # Fallback to temp file if ephemeral directory writing fails
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(raw_bytes)
                    tmp_path_to_clean = Path(tmp.name)
                target_path = tmp_path_to_clean
                target_filename = raw_filename

        try:
            start_page = int(form.get("start_page", 1))
            if start_page < 1:
                raise ValueError("start_page must be >= 1")
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="start_page must be an integer >= 1")

        raw_end = form.get("end_page")
        if raw_end is not None and str(raw_end).strip() != "":
            try:
                end_page = int(raw_end)
                if end_page < start_page:
                    raise ValueError("end_page must be >= start_page")
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="end_page must be an integer >= start_page")

        language = str(form.get("language", "auto")).lower()
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF file upload or document_id is required. Drive storage lookup is disabled.",
        )

    if language not in ("auto", "ar", "en", "mixed"):
        language = "auto"

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=422, detail="Unable to resolve document file path.")

    try:
        validate_upload_size(target_path.stat().st_size)
        validate_pdf_pages(target_path)
        data = await run_in_threadpool(
            AdvancedOcrService().extract,
            target_path,
            start_page=start_page,
            end_page=end_page,
            language=language,
        )
        return {
            **data,
            "status": "success",
            "document_id": target_doc_id,
            "filename": target_filename,
            "ttl_minutes": e_doc.ttl_minutes if e_doc else settings.DOC_TTL_MINUTES,
            "remaining_seconds": e_doc.remaining_seconds if e_doc else None,
            "expires_at": e_doc.expires_at.isoformat() if e_doc else None,
        }
    except UploadSizeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OcrError as exc:
        logger.warning("Advanced OCR failed for file %s: %s", target_filename, exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        if tmp_path_to_clean and tmp_path_to_clean.exists():
            tmp_path_to_clean.unlink(missing_ok=True)


@router.get("/ocr/document/{doc_id}", summary="Extract Layout-Aware Document Blocks")
def pipeline_get_document_ocr_blocks(
    doc_id: str,
    page: Optional[int] = Query(None, description="Optional 1-indexed page number"),
    language: str = Query("auto", description="Target language: 'auto', 'ar' (Arabic), 'en' (English), or 'mixed'"),
    force_ocr: bool = Query(False, description="Force vision-based OCR re-extraction"),
    account: CompanyAccount = CompanyAuth,
):
    """
    Retrieve structured layout blocks from a document (titles, text, metadata,
    tables with content_md, and images with descriptions) with Arabic and English support.
    """
    from backend.agent.tools.ocr import OcrService

    file_path, filename = _resolve_document_file_path(doc_id)
    ocr_service = OcrService()
    try:
        data = ocr_service.ocr_extract_blocks(file_path, page_number=page, language=language, force_ocr=force_ocr)
        return {
            "status": "success",
            "document_id": doc_id,
            "filename": filename,
            "total_pages": data.get("total_pages", 1),
            "page": page,
            "language_detected": data.get("language_detected", language),
            "direction": data.get("direction", "rtl" if language == "ar" else "ltr"),
            "ocr_text": data.get("ocr_text", ""),
            "coordinate_system": data.get("coordinate_system", "normalized_0_1000"),
            "blocks": data.get("blocks", []),
            "pages": data.get("pages", []),
        }
    except Exception as exc:
        logger.error("OCR block extraction failed for %s: %s", doc_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR block extraction failed: {exc}",
        )


@router.post("/ocr/blocks", summary="Extract Layout Blocks from Document")
def pipeline_post_ocr_blocks(
    payload: OcrBlocksPayload,
    account: CompanyAccount = CompanyAuth,
):
    """Extract structural layout blocks with titles, text, tables (content_md), and images."""
    return pipeline_get_document_ocr_blocks(
        doc_id=payload.document_id,
        page=payload.page,
        language=payload.language,
        force_ocr=payload.force_ocr,
        account=account,
    )


@router.post("/ocr/page/blocks", summary="Extract Bilingual Arabic & English Layout Blocks by Page")
def pipeline_post_page_ocr_blocks(
    payload: OcrPageBlocksPayload,
    account: CompanyAccount = CompanyAuth,
):
    """
    Extract bilingual Arabic and English layout blocks for a specific page.
    Returns blocks with reading direction, language classification, markdown tables, and visual descriptions.
    """
    from backend.agent.tools.ocr import OcrService

    file_path, filename = _resolve_document_file_path(payload.document_id)
    ocr_service = OcrService()
    try:
        data = ocr_service.ocr_read_page_blocks(
            file_path,
            page_number=payload.page_number,
            language=payload.language,
            force_ocr=payload.force_ocr,
        )
        return {
            "status": "success",
            "document_id": payload.document_id,
            "filename": filename,
            "page_number": payload.page_number,
            "language_detected": data.get("language_detected", payload.language),
            "direction": data.get("direction", "rtl" if payload.language == "ar" else "ltr"),
            "block_count": data.get("block_count", len(data.get("blocks", []))),
            "ocr_text": data.get("ocr_text", ""),
            "coordinate_system": data.get("coordinate_system", "normalized_0_1000"),
            "blocks": data.get("blocks", []),
        }
    except Exception as exc:
        logger.error("Page OCR block extraction failed for %s (page %d): %s", payload.document_id, payload.page_number, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Page OCR extraction failed: {exc}",
        )


@router.get("/ocr/document/{doc_id}/page/{page_number}/blocks", summary="Extract Layout Blocks for Specific Page")
def pipeline_get_page_ocr_blocks(
    doc_id: str,
    page_number: int,
    language: str = Query("auto", description="Target language: 'auto', 'ar', 'en', 'mixed'"),
    force_ocr: bool = Query(False, description="Force vision-based OCR re-extraction"),
    account: CompanyAccount = CompanyAuth,
):
    """Retrieve bilingual layout blocks for a specific page number."""
    from backend.agent.tools.ocr import OcrService

    file_path, filename = _resolve_document_file_path(doc_id)
    ocr_service = OcrService()
    try:
        data = ocr_service.ocr_read_page_blocks(
            file_path,
            page_number=page_number,
            language=language,
            force_ocr=force_ocr,
        )
        return {
            "status": "success",
            "document_id": doc_id,
            "filename": filename,
            "page_number": page_number,
            "language_detected": data.get("language_detected", language),
            "direction": data.get("direction", "rtl" if language == "ar" else "ltr"),
            "block_count": data.get("block_count", len(data.get("blocks", []))),
            "ocr_text": data.get("ocr_text", ""),
            "coordinate_system": data.get("coordinate_system", "normalized_0_1000"),
            "blocks": data.get("blocks", []),
        }
    except Exception as exc:
        logger.error("Page OCR block extraction failed for %s (page %d): %s", doc_id, page_number, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Page OCR extraction failed: {exc}",
        )


@router.post("/pipeline/run", summary="Execute Pipeline Document AI Service")
async def pipeline_run_service(
    payload: PipelineRunPayload,
    response: Response,
    background_tasks: BackgroundTasks,
    account: CompanyAccount = CompanyAuth,
):
    """
    Execute a specialized Document AI agent in the enterprise pipeline.
    Supports structured JSON extraction, automated billing deduction, and webhook notification.
    """
    service_name = payload.service.lower().replace("-", "_")
    if service_name not in SERVICE_PRICING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown service '{payload.service}'. Supported: {', '.join(SERVICE_PRICING.keys())}",
        )

    cost = billing_service.get_service_cost(service_name)
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. Required: {cost}, Remaining: {account.remaining_credits}.",
        )

    # Load bundle from document_id or text_content
    target_doc_id = payload.document_id
    e_doc = None
    if target_doc_id:
        e_doc = ephemeral_store.get_and_touch(target_doc_id, extend_ttl=True)
        try:
            bundle = rag.get_bundle(target_doc_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{target_doc_id}' not found: {exc}",
            )
    elif payload.text_content and payload.text_content.strip():
        bundle = rag.create_text_bundle(payload.text_content.strip(), name=f"{service_name}_text.txt")
        target_doc_id = bundle.doc_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'document_id' or 'text_content' must be provided.",
        )

    if bundle.vector_store is None:
        raise HTTPException(status_code=400, detail="Document index not ready.")

    # Deduct credits
    try:
        remaining = billing_service.check_and_deduct_credits(
            account=account,
            service_name=service_name,
            document_id=target_doc_id,
            request_summary=payload.query or f"Pipeline run: {service_name}",
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))

    model = payload.model or settings.DEFAULT_MODEL
    task_prompt = payload.query or f"Perform complete {service_name} processing and structured analysis."

    effective_system_prompt = payload.system_prompt
    if payload.schema_override:
        schema_dump = (
            json.dumps(payload.schema_override, indent=2, ensure_ascii=False)
            if isinstance(payload.schema_override, (dict, list))
            else str(payload.schema_override)
        )
        schema_inst = (
            f"\n\nOUTPUT SCHEMA REQUIREMENT:\n"
            f"You MUST format and return your final response strictly as a JSON object adhering to this schema/structure:\n"
            f"```json\n{schema_dump}\n```\n"
            f"Return ONLY valid JSON matching this schema."
        )
        if effective_system_prompt:
            effective_system_prompt += schema_inst
        else:
            task_prompt += schema_inst

    agent = rag._build_agent(bundle, model, mode=service_name, system_prompt=effective_system_prompt)


    try:
        result = await run_in_threadpool(agent.run, task_prompt)
        if not result.success:
            remaining = billing_service.refund_credits(
                account=account,
                service_name=service_name,
                credits_to_refund=cost,
                document_id=payload.document_id,
                reason=result.error or f"{service_name} execution failed",
            )
            resp_body = {
                "status": "failed",
                "service": service_name,
                "documentId": payload.document_id,
                "creditsDeducted": 0,
                "creditsRefunded": cost,
                "creditsRemaining": remaining,
                "success": False,
                "error": result.error,
                "raw": result.response or "",
            }
            if payload.webhook_url:
                background_tasks.add_task(_dispatch_webhook, payload.webhook_url, resp_body)
            response.headers["X-Credits-Cost"] = "0"
            response.headers["X-Credits-Remaining"] = str(remaining)
            return resp_body

    except Exception as exc:
        logger.exception("Pipeline run exception for %s: %s", service_name, exc)
        remaining = billing_service.refund_credits(
            account=account,
            service_name=service_name,
            credits_to_refund=cost,
            document_id=payload.document_id,
            reason=f"Pipeline exception: {exc}",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Execution error: {exc}. Credits refunded (Remaining: {remaining}).",
        )

    # Parse structured JSON if applicable
    raw_text = result.response or ""
    parsed_json = _extract_json_from_text(raw_text)

    # Check steps for tool observations if not in final response
    if parsed_json is None and hasattr(result, "steps") and result.steps:
        for step in reversed(result.steps):
            obs = step.get("observation", "")
            if isinstance(obs, str) and ("{" in obs or "[" in obs):
                step_json = _extract_json_from_text(obs)
                if step_json:
                    parsed_json = step_json
                    break

    # If JSON output is requested or it is a structured extraction service, guarantee structured data
    is_structured_service = service_name in [
        "invoice", "receipt", "contract", "compliance", "form_parser", "financial_statement", "redaction", "classifier"
    ]
    if (payload.output_format == "json" or is_structured_service) and parsed_json is None:
        parsed_json = extract_structured_data(raw_text, service=service_name)

    response_data: Dict[str, Any] = {
        "status": "success",
        "service": service_name,
        "documentId": payload.document_id,
        "creditsDeducted": cost,
        "creditsRemaining": remaining,
        "success": True,
        "raw": raw_text,
    }

    if e_doc:
        response_data["ttlMinutes"] = e_doc.ttl_minutes
        response_data["remainingSeconds"] = e_doc.remaining_seconds
        response_data["expiresAt"] = e_doc.expires_at.isoformat()

    if payload.output_format == "json" or parsed_json is not None:
        response_data["data"] = parsed_json

    response.headers["X-Credits-Cost"] = str(cost)
    response.headers["X-Credits-Remaining"] = str(remaining)

    if payload.webhook_url:
        background_tasks.add_task(_dispatch_webhook, payload.webhook_url, response_data)

    return response_data


@router.post("/pipeline/batch", summary="Batch Pipeline Execution")
async def pipeline_batch_run(
    payload: PipelineBatchPayload,
    background_tasks: BackgroundTasks,
    account: CompanyAccount = CompanyAuth,
):
    """
    Execute multiple pipeline document tasks in a single batch request.
    Collects results and can trigger an asynchronous webhook when complete.
    """
    results = []
    total_cost = 0

    for task in payload.tasks:
        sub_payload = PipelineRunPayload(
            document_id=task.document_id,
            service=task.service,
            query=task.query,
            output_format=task.output_format,
        )
        dummy_resp = Response()
        try:
            res = await pipeline_run_service(
                payload=sub_payload,
                response=dummy_resp,
                background_tasks=background_tasks,
                account=account,
            )
            results.append(res)
            total_cost += res.get("creditsDeducted", 0)
        except Exception as exc:
            results.append(
                {
                    "status": "failed",
                    "documentId": task.document_id,
                    "service": task.service,
                    "error": str(exc),
                    "success": False,
                }
            )

    batch_summary = {
        "status": "completed",
        "totalTasks": len(payload.tasks),
        "totalCost": total_cost,
        "creditsRemaining": account.remaining_credits,
        "results": results,
    }

    if payload.webhook_url:
        background_tasks.add_task(_dispatch_webhook, payload.webhook_url, batch_summary)

    return batch_summary


# ---------------------------------------------------------------------------
# Asynchronous Background Job Endpoints (Redis / Worker Queue)
# ---------------------------------------------------------------------------


class AsyncJobSubmitPayload(BaseModel):
    document_id: str
    service: str
    query: Optional[str] = None
    output_format: Literal["json", "markdown", "auto"] = "auto"
    webhook_url: Optional[str] = None


@router.post("/pipeline/jobs", status_code=status.HTTP_202_ACCEPTED, summary="Submit Async Pipeline Job")
async def submit_async_pipeline_job(
    payload: AsyncJobSubmitPayload,
    account: CompanyAccount = CompanyAuth,
):
    """
    Submit a long-running document intelligence job to the Redis worker queue.
    Returns immediately with HTTP 202 and a job_id for polling or webhook callback.
    """
    service_name = payload.service.lower().replace("-", "_")
    if service_name not in SERVICE_PRICING:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown service '{payload.service}'. Supported: {', '.join(SERVICE_PRICING.keys())}",
        )

    cost = billing_service.get_service_cost(service_name)
    if account.remaining_credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits for {service_name}. Required: {cost}, Remaining: {account.remaining_credits}.",
        )

    job = job_queue.enqueue(
        service=service_name,
        document_id=payload.document_id,
        user_id=str(account.user_id),
        company_id=str(account.id),
        query=payload.query,
        output_format=payload.output_format,
        webhook_url=payload.webhook_url,
    )

    return {
        "status": "accepted",
        "jobId": job.id,
        "service": job.service,
        "documentId": job.document_id,
        "state": job.status,
        "estimatedCredits": cost,
        "pollUrl": f"/api/v1/pipeline/jobs/{job.id}",
        "createdAt": job.created_at,
    }


@router.get("/pipeline/jobs/{job_id}", summary="Get Async Pipeline Job Status")
def get_async_pipeline_job(
    job_id: str,
    account: CompanyAccount = CompanyAuth,
):
    """Poll the status, progress (0-100), and result of a background job."""
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    return {
        "jobId": job.id,
        "service": job.service,
        "documentId": job.document_id,
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
        "createdAt": job.created_at,
        "updatedAt": job.updated_at,
        "completedAt": job.completed_at,
    }


@router.get("/pipeline/jobs", summary="List Company Pipeline Jobs")
def list_async_pipeline_jobs(
    limit: int = Query(50, ge=1, le=200),
    account: CompanyAccount = CompanyAuth,
):
    """List recent background pipeline jobs."""
    jobs = job_queue.list_jobs(limit=limit, user_id=str(account.user_id))
    return {
        "total": len(jobs),
        "jobs": [j.to_dict() for j in jobs],
    }


# ---------------------------------------------------------------------------
# SeaweedFS S3 Storage Endpoints
# ---------------------------------------------------------------------------


@router.get("/storage/status", summary="Check SeaweedFS S3 Storage Status")
def get_storage_status(account: CompanyAccount = CompanyAuth):
    """Inspect SeaweedFS S3 storage health."""
    healthy = storage_service.is_healthy()
    return {
        "provider": "SeaweedFS (S3-Compatible)",
        "endpoint": storage_service.public_endpoint,
        "bucket": storage_service.bucket,
        "isHealthy": healthy,
        "storageBackend": "seaweedfs",
    }


@router.get("/storage/documents/{doc_id}/presigned-url", summary="Generate Expiring Download URL")
def get_document_presigned_url(
    doc_id: str,
    expires_seconds: int = Query(3600, ge=60, le=86400),
    account: CompanyAccount = CompanyAuth,
):
    """Generate a secure presigned GET URL for client document downloads."""
    # Look up document original filename
    try:
        doc = query("SELECT original_filename FROM docuchat.documents WHERE id = %s", (doc_id,), one=True)
        fname = doc["original_filename"] if doc else f"{doc_id}.pdf"
    except Exception:
        fname = f"{doc_id}.pdf"

    object_name = f"documents/{doc_id}/{fname}"
    # Publish existing ingestion files to the object store when first requested.
    if not storage_service.exists(object_name):
        source, _ = _resolve_document_file_path(doc_id)
        storage_service.upload(object_name, source)
    url = storage_service.get_presigned_url(object_name, expires_seconds=expires_seconds)
    return {
        "documentId": doc_id,
        "objectName": object_name,
        "url": url,
        "expiresInSeconds": expires_seconds,
    }


# ---------------------------------------------------------------------------
# ChatGPT Custom GPTs & OpenAI Tool Calling Endpoints
# ---------------------------------------------------------------------------


@router.get("/gpt/openapi.json", summary="OpenAPI Specification for ChatGPT Actions")
def get_chatgpt_actions_openapi():
    """
    Returns an OpenAPI 3.1 specification optimized for ChatGPT Custom GPT Actions.
    Enter this URL in ChatGPT's 'Create a GPT' -> 'Configure' -> 'Actions' -> 'Import from URL'.
    """
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "DOCTool B2B Document AI API",
            "version": "1.0.0",
            "description": "Enterprise Document Intelligence API: invoice extraction, contract analysis, PII audit, search, and RAG Q&A.",
        },
        "servers": [
            {
                "url": "http://127.0.0.1:8000/api/v1",
                "description": "Local DOCTool Server",
            }
        ],
        "paths": {
            "/documents": {
                "get": {
                    "operationId": "listDocuments",
                    "summary": "List available documents",
                    "responses": {"200": {"description": "List of indexed documents"}},
                }
            },
            "/documents/{doc_id}/search": {
                "get": {
                    "operationId": "searchDocumentChunks",
                    "summary": "Search document content with hybrid vector and keyword search",
                    "parameters": [
                        {"name": "doc_id", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "query", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "top_k", "in": "query", "schema": {"type": "integer", "default": 5}},
                    ],
                    "responses": {"200": {"description": "Matching chunk snippets and citations"}},
                }
            },
            "/pipeline/run": {
                "post": {
                    "operationId": "runDocumentAiService",
                    "summary": "Run AI service on document (invoice, contract, compliance, summary, form_parser)",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["document_id", "service"],
                                    "properties": {
                                        "document_id": {"type": "string"},
                                        "service": {
                                            "type": "string",
                                            "enum": [
                                                "invoice",
                                                "contract",
                                                "compliance",
                                                "summary",
                                                "form_parser",
                                                "receipt",
                                                "resume",
                                                "research",
                                                "redaction",
                                                "classifier",
                                                "financial_statement",
                                                "translation",
                                                "anomaly_audit",
                                                "chat",
                                            ],
                                        },
                                        "query": {"type": "string"},
                                        "output_format": {"type": "string", "enum": ["json", "markdown", "auto"]},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Service analysis result"}},
                }
            },
        },
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                }
            }
        },
        "security": [{"ApiKeyAuth": []}],
    }


@router.get("/openai/tools", summary="OpenAI Function Calling Tools Specification")
def get_openai_function_tools():
    """
    Returns OpenAI-compatible function calling schemas (`tools` parameter)
    for direct integration into GPT chats (`client.chat.completions.create`).
    """
    return {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "docuchat_list_documents",
                    "description": "List documents uploaded to DOCTool with their page count and IDs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Maximum documents to return", "default": 20}
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_search_chunks",
                    "description": "Hybrid semantic and keyword search across document chunks with page citations.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id", "query"],
                        "properties": {
                            "document_id": {"type": "string", "description": "ID of document to search"},
                            "query": {"type": "string", "description": "Keywords or semantic question"},
                            "top_k": {"type": "integer", "description": "Number of snippets to retrieve", "default": 5},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_extract_invoice",
                    "description": "Extract structured financial invoice data (vendor, line items, taxes, totals).",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                            "query": {"type": "string", "description": "Optional specific extraction prompt"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_analyze_contract",
                    "description": "Analyze contract clauses, legal liabilities, indemnities, and termination terms.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                            "query": {"type": "string", "description": "Optional specific legal focus area"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_audit_compliance",
                    "description": "Scan document for PII, GDPR/HIPAA compliance risks, and security flags.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_summarize_document",
                    "description": "Generate multi-section executive summary with grounded citations.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                            "query": {"type": "string", "description": "Optional summary focus"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_redact_document",
                    "description": "Sanitize and redact sensitive PII (National IDs, Iqama, IBANs, Credit Cards, Phones) in English and Arabic.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                            "query": {"type": "string", "description": "Optional specific redaction instructions"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_classify_document",
                    "description": "Classify document category, language, and routing department in English and Arabic.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_analyze_financial_statement",
                    "description": "Extract financial statement metrics (revenue, EBIT, net income, assets, equity) and compute financial ratios in EN & AR.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                            "query": {"type": "string", "description": "Optional financial focus"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_translate_document",
                    "description": "Bidirectional certified enterprise translation between English and Arabic (EN <-> AR) preserving clauses and tables.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                            "target_language": {"type": "string", "description": "Target language: Arabic or English", "default": "Arabic"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docuchat_audit_anomalies",
                    "description": "Forensic audit for arithmetic errors, ZATCA VAT 15%, inverted dates, and contractual contradictions in EN & AR.",
                    "parameters": {
                        "type": "object",
                        "required": ["document_id"],
                        "properties": {
                            "document_id": {"type": "string", "description": "Document ID"},
                            "query": {"type": "string", "description": "Optional audit focus"},
                        },
                    },
                },
            },
        ]
    }


# ---------------------------------------------------------------------------
# Account & Pricing Endpoints
# ---------------------------------------------------------------------------


@router.get("/company/account", summary="Get Company Balance and Tier")
def get_company_account_v1(account: CompanyAccount = CompanyAuth):
    """Get company account details, remaining free trial credits, and usage stats."""
    return {
        "companyId": account.id,
        "companyName": account.company_name,
        "planTier": account.plan_tier,
        "totalCredits": account.total_credits,
        "usedCredits": account.used_credits,
        "remainingCredits": account.remaining_credits,
        "apiKeyPrefix": account.api_key_prefix,
        "createdAt": account.created_at,
    }


@router.get("/company/pricing", summary="Get B2B Service Pricing Catalog")
def get_service_pricing_catalog():
    """Retrieve catalog of Document AI services and credit rates."""
    return {
        "initialTrialCredits": INITIAL_TRIAL_CREDITS,
        "services": [
            {
                "id": k,
                "name": v["name"],
                "credits": v["credits"],
                "llmTier": v["llm_tier"],
                "category": v["category"],
                "description": v["description"],
            }
            for k, v in SERVICE_PRICING.items()
        ],
    }


@router.get("/models", summary="List Available AI Models", tags=["Models"])
def list_available_models():
    """Retrieve available AI models for document intelligence.

    Currently configured: 'gpt-6-luna' (Luna) for high-performance vision OCR,
    structured schema generation, and bilingual Arabic/English document reasoning.
    """
    model_name = settings.DEFAULT_MODEL or "gpt-6-luna"
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "name": "Luna (GPT-6 Luna)",
                "description": "High-accuracy vision, layout-aware semantic OCR, and bilingual reasoning engine.",
                "capabilities": ["vision", "semantic_ocr", "arabic_english", "structured_json", "rag"],
                "context_window": 128000,
                "status": "available",
                "is_default": True,
            }
        ],
        "default_model": model_name,
        "total_available": 1,
    }
