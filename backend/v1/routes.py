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
from backend.jobs import job_queue
from backend.storage import storage_service

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
    document_id: str = Field(..., description="Target document ID")
    service: str = Field(
        "summary",
        description="Service: invoice, contract, compliance, summary, form_parser, receipt, resume, research, chat",
    )
    query: Optional[str] = Field(None, description="Optional custom prompt or question")
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
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try fenced code blocks ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Try curly brackets
    curly = re.search(r"(\{[\s\S]*\})", text)
    if curly:
        try:
            return json.loads(curly.group(1))
        except Exception:
            pass

    return None


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
        raw_bytes = await uploaded_file.read(50 * 1024 * 1024 + 1)
        if not raw_bytes or len(raw_bytes) > 50 * 1024 * 1024:
            raise HTTPException(413, "Document size must be between 1 byte and 50 MB.")
        mime_type = uploaded_file.content_type or "application/octet-stream"
    else:
        # Raw bytes stream
        raw_bytes = await request.body()
        if not raw_bytes:
            raise HTTPException(400, "Empty upload payload.")
        filename = request.headers.get("X-Filename", "document.txt")
        mime_type = content_type or "application/octet-stream"

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

    return {
        "status": "success",
        "documentId": doc_id,
        "filename": filename,
        "fileSize": file_size,
        "pageCount": page_count,
        "chunkCount": chunk_count,
        "creditsRemaining": account.remaining_credits,
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

    # Load bundle
    try:
        bundle = rag.get_bundle(payload.document_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{payload.document_id}' not found: {exc}",
        )

    if bundle.vector_store is None:
        raise HTTPException(status_code=400, detail="Document index not ready.")

    # Deduct credits
    try:
        remaining = billing_service.check_and_deduct_credits(
            account=account,
            service_name=service_name,
            document_id=payload.document_id,
            request_summary=payload.query or f"Pipeline run: {service_name}",
        )
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc))

    model = payload.model or settings.DEFAULT_MODEL
    agent = rag._build_agent(bundle, model, mode=service_name)
    task_prompt = payload.query or f"Perform complete {service_name} processing and structured analysis."

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

    response_data: Dict[str, Any] = {
        "status": "success",
        "service": service_name,
        "documentId": payload.document_id,
        "creditsDeducted": cost,
        "creditsRemaining": remaining,
        "success": True,
        "raw": raw_text,
    }

    if payload.output_format == "json" or parsed_json is not None:
        response_data["data"] = parsed_json or {"raw": raw_text}

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
# MinIO Object Storage Endpoints
# ---------------------------------------------------------------------------


@router.get("/storage/status", summary="Check MinIO Object Storage Status")
def get_storage_status(account: CompanyAccount = CompanyAuth):
    """Inspect MinIO object storage health, active bucket, and endpoint."""
    healthy = storage_service.is_healthy()
    return {
        "provider": "MinIO (S3-Compatible)",
        "endpoint": settings.MINIO_ENDPOINT,
        "bucket": settings.MINIO_BUCKET,
        "isHealthy": healthy,
        "storageBackend": "minio" if healthy else "local_fallback",
    }


@router.get("/storage/documents/{doc_id}/presigned-url", summary="Generate MinIO Presigned URL")
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
