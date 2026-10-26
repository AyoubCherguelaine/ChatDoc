"""
Asynchronous Pipeline Job Worker.

Processes background document intelligence jobs, updates status,
and dispatches webhook callbacks when tasks complete.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import threading
import time

import httpx

from backend import rag
from backend.billing import billing_service
from backend.config import settings
from backend.jobs.queue import Job, job_queue

logger = logging.getLogger("docuchat.worker")


async def _send_webhook(url: str, payload: dict) -> None:
    """Send cryptographically signed HMAC-SHA256 webhook notification to pipeline consumer."""
    try:
        raw_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        timestamp = str(int(time.time()))
        signing_secret = settings.JWT_SECRET
        signature = hmac.new(
            signing_secret.encode("utf-8"),
            f"{timestamp}.".encode("utf-8") + raw_body,
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-DocuChat-Timestamp": timestamp,
            "X-DocuChat-Signature": f"sha256={signature}",
            "User-Agent": "DocuChat-Enterprise-Worker/1.0",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=raw_body, headers=headers)
            logger.info("Webhook dispatched to %s, status=%d", url, resp.status_code)
    except Exception as exc:
        logger.warning("Failed to dispatch webhook to %s: %s", url, exc)


def execute_job_task(job: Job) -> Job:
    """Execute a single background pipeline job synchronously or within a worker thread."""
    logger.info("Starting execution of job %s (service: %s, doc: %s)", job.id, job.service, job.document_id)
    job_queue.update_job(job.id, status="processing", progress=15)

    service_name = job.service.lower().replace("-", "_")
    cost = billing_service.get_service_cost(service_name)

    # 1. Billing verification & deduction
    account = None
    if job.company_id:
        account = billing_service.get_company_by_id(job.company_id)
    if not account and job.user_id:
        account = billing_service.get_or_create_company(job.user_id)

    if account and account.remaining_credits < cost:
        err_msg = f"Insufficient credits for {service_name}. Required: {cost}, Remaining: {account.remaining_credits}."
        job = job_queue.update_job(job.id, status="failed", error=err_msg, progress=100) or job
        return job

    if account:
        try:
            billing_service.check_and_deduct_credits(
                account=account,
                service_name=service_name,
                document_id=job.document_id,
                request_summary=job.query or f"Async Job: {service_name}",
            )
        except Exception as exc:
            job = job_queue.update_job(job.id, status="failed", error=str(exc), progress=100) or job
            return job

    job = job_queue.update_job(job.id, progress=35) or job

    # 2. Document Bundle loading
    try:
        bundle = rag.get_bundle(job.document_id)
    except Exception as exc:
        if account:
            billing_service.refund_credits(account, service_name, cost, job.document_id, f"Document load error: {exc}")
        job = job_queue.update_job(job.id, status="failed", error=f"Failed to load document: {exc}", progress=100) or job
        return job

    if bundle.vector_store is None:
        if account:
            billing_service.refund_credits(account, service_name, cost, job.document_id, "Document index not ready")
        job = job_queue.update_job(job.id, status="failed", error="Document vector store index is not ready.", progress=100) or job
        return job

    job = job_queue.update_job(job.id, progress=55) or job

    # 3. Agent execution
    agent = rag._build_agent(bundle, settings.DEFAULT_MODEL, mode=service_name)
    task_prompt = job.query or f"Perform full {service_name} intelligence analysis on document."

    try:
        res = agent.run(task_prompt)
        if not res.success:
            if account:
                billing_service.refund_credits(account, service_name, cost, job.document_id, res.error or "Agent failed")
            job = job_queue.update_job(job.id, status="failed", error=res.error or "Execution failed", progress=100) or job
            return job

        # Format result
        from backend.v1.routes import _extract_json_from_text

        raw_text = res.response or ""
        parsed_json = _extract_json_from_text(raw_text)

        result_payload = {
            "status": "success",
            "jobId": job.id,
            "service": service_name,
            "documentId": job.document_id,
            "creditsCost": cost,
            "creditsRemaining": account.remaining_credits if account else 0,
            "data": parsed_json if (job.output_format == "json" or parsed_json) else None,
            "raw": raw_text,
        }

        job = job_queue.update_job(job.id, status="completed", progress=100, result=result_payload)
        logger.info("Job %s completed successfully", job.id)

        # Trigger webhook if specified
        if job.webhook_url:
            asyncio.run(_send_webhook(job.webhook_url, result_payload))

        return job

    except Exception as exc:
        logger.exception("Job %s raised unhandled exception: %s", job.id, exc)
        if account:
            billing_service.refund_credits(account, service_name, cost, job.document_id, f"Worker exception: {exc}")
        job = job_queue.update_job(job.id, status="failed", error=str(exc), progress=100)
        return job


def run_worker_loop(stop_check=None) -> None:
    """Continuous polling worker loop for processing queued jobs."""
    logger.info("DocuChat background job worker started. Listening for jobs...")
    while True:
        if stop_check and stop_check():
            break

        job_id = job_queue.pop_job(timeout_seconds=2)
        if not job_id:
            time.sleep(0.1)
            continue

        job = job_queue.get_job(job_id)
        if not job:
            continue

        execute_job_task(job)


def start_background_worker() -> threading.Thread:
    """Start the worker loop in a daemon thread inside the FastAPI application."""
    thread = threading.Thread(target=run_worker_loop, daemon=True, name="DocuChatJobWorker")
    thread.start()
    return thread


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run_worker_loop()
