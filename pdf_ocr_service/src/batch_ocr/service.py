from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arabic_pdf_md_agent.base.prompts import normalize_model_markdown
from arabic_pdf_md_agent.base.schemas import DocumentExtractionResult, PageExtractionResult, dataclass_to_json
from arabic_pdf_md_agent.base.utils import (
    count_arabic_characters,
    is_probably_pdf,
    resolve_pdf_inputs,
    safe_file_stem,
    utc_now_iso,
    write_json,
    write_text,
)
from arabic_pdf_md_agent.batch_ocr.gemini_batch_client import GeminiBatchClient, GeminiBatchError
from arabic_pdf_md_agent.batch_ocr.schemas import BatchCollectSummary, BatchOcrConfig, UsageRecord
from arabic_pdf_md_agent.batch_ocr.usage_db import GeminiUsageStore
from arabic_pdf_md_agent.pdf_ocr_service.db.manifest_store import ManifestStore
from arabic_pdf_md_agent.pdf_ocr_service.prompts import build_ocr_prompt
from arabic_pdf_md_agent.pdf_ocr_service.service import PdfOcrService
from arabic_pdf_md_agent.pdf_ocr_service.tools.pdf_renderer import PdfRenderer

logger = logging.getLogger(__name__)

TERMINAL_STATES = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}


class GeminiBatchOcrService:
    """Image-only Gemini Batch OCR pipeline for Arabic regulation PDFs."""

    def __init__(
        self,
        *,
        renderer: PdfRenderer | None = None,
        client: GeminiBatchClient | None = None,
    ) -> None:
        self.renderer = renderer or PdfRenderer()
        self.client = client

    def prepare(self, config: BatchOcrConfig) -> dict[str, Any]:
        run_id = config.run_id or self._new_run_id()
        workspace = self._workspace(config.output_dir, run_id)
        images_dir = workspace / "images"
        workspace.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        client = self._client(config)
        usage_store = self._usage_store(config)
        usage_store.initialize()

        manifest: dict[str, Any] = {
            "run_id": run_id,
            "model": config.model,
            "status": "prepared",
            "input_pdf": str(config.input_pdf) if config.input_pdf else None,
            "input_dir": str(config.input_dir),
            "output_dir": str(config.output_dir),
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "pages": [],
            "documents": [],
        }

        total_pages = 0
        try:
            for pdf_path in resolve_pdf_inputs(
                input_pdf=config.input_pdf,
                input_dir=config.input_dir,
                include_glob=config.include_glob,
                recursive=config.recursive,
            ):
                md_path = config.output_dir / f"{safe_file_stem(pdf_path.stem)}.md"
                if md_path.exists() and not config.overwrite:
                    manifest["documents"].append(
                        {
                            "pdf_path": str(pdf_path),
                            "pdf_stem": pdf_path.stem,
                            "status": "skipped_existing",
                            "total_pages": 0,
                        }
                    )
                    continue

                if not is_probably_pdf(pdf_path):
                    manifest["documents"].append(
                        {
                            "pdf_path": str(pdf_path),
                            "pdf_stem": pdf_path.stem,
                            "status": "invalid_pdf",
                            "total_pages": 0,
                            "error": "File does not have a valid %PDF header signature",
                        }
                    )
                    continue

                page_count = self.renderer.page_count(pdf_path)
                page_limit = min(page_count, config.max_pages_per_pdf) if config.max_pages_per_pdf else page_count
                manifest["documents"].append(
                    {
                        "pdf_path": str(pdf_path),
                        "pdf_stem": pdf_path.stem,
                        "status": "queued",
                        "total_pages": page_limit,
                    }
                )
                for page_number, image_bytes in self.renderer.iter_rendered_pages(
                    pdf_path=pdf_path,
                    dpi=config.dpi,
                    max_pages=page_limit,
                ):
                    request_key = self._request_key(pdf_path, page_number)
                    image_path = images_dir / f"{request_key}.png"
                    image_path.write_bytes(image_bytes)
                    try:
                        uploaded = client.upload_file(
                            image_path,
                            display_name=f"{run_id}-{request_key}",
                            mime_type="image/png",
                        )
                        file_info = uploaded.get("file", uploaded)
                        file_uri = str(file_info.get("uri") or "").strip()
                        file_name = str(file_info.get("name") or "").strip()
                        if not file_uri:
                            raise GeminiBatchError(f"Gemini upload response missing file uri: {uploaded}")
                        status = "uploaded"
                        error = None
                    except Exception as upload_error:
                        file_uri = ""
                        file_name = ""
                        status = "upload_failed"
                        error = str(upload_error)
                        logger.warning("Failed to upload %s page %s: %s", pdf_path.name, page_number, upload_error)

                    manifest["pages"].append(
                        {
                            "request_key": request_key,
                            "pdf_path": str(pdf_path),
                            "pdf_stem": pdf_path.stem,
                            "page_number": page_number,
                            "total_pages": page_limit,
                            "image_path": str(image_path),
                            "file_name": file_name,
                            "file_uri": file_uri,
                            "status": status,
                            "error": error,
                        }
                    )
                    total_pages += 1

            self._write_requests_jsonl(manifest=manifest, path=workspace / "requests.jsonl")
            self._save_manifest(config.output_dir, run_id, manifest)
            self._write_latest_run_id(config.output_dir, run_id)
            usage_store.upsert_run(
                run_id=run_id,
                model=config.model,
                input_dir=config.input_dir,
                output_dir=config.output_dir,
                status="prepared",
                input_price_per_1m_usd=config.input_cost_usd_per_1m_tokens,
                output_price_per_1m_usd=config.output_cost_usd_per_1m_tokens,
                total_pdfs=len(manifest["documents"]),
                total_pages=total_pages,
            )
            return manifest
        finally:
            self._close_client(client)

    def submit(self, config: BatchOcrConfig) -> dict[str, Any]:
        run_id = self._resolve_run_id(config)
        manifest = self._load_manifest(config.output_dir, run_id)
        workspace = self._workspace(config.output_dir, run_id)
        client = self._client(config)
        try:
            request_count = self._uploaded_request_count(manifest)
            if request_count <= 0:
                raise RuntimeError(self._no_uploaded_pages_error(manifest))

            uploaded_file = client.upload_file(
                workspace / "requests.jsonl",
                display_name=f"{run_id}-batch-requests",
                mime_type="application/jsonl",
            )
            input_file = uploaded_file.get("file", uploaded_file)
            input_file_name = str(input_file.get("name") or "").strip()
            if not input_file_name:
                raise GeminiBatchError(f"Gemini JSONL upload response missing file name: {uploaded_file}")

            job = client.create_batch(input_file_name, display_name=f"arabic-pdf-md-{run_id}")
            batch_name = GeminiBatchClient.batch_name(job)
            manifest["status"] = "submitted"
            manifest["batch_job_name"] = batch_name
            manifest["batch_input_file_name"] = input_file_name
            manifest["updated_at"] = utc_now_iso()
            self._save_manifest(config.output_dir, run_id, manifest)
            write_json(workspace / "job.json", {"run_id": run_id, "batch_job_name": batch_name, "job": job})
            self._usage_store(config).update_run_status(run_id, "submitted", batch_name)
            return {"run_id": run_id, "batch_job_name": batch_name, "job": job}
        finally:
            self._close_client(client)

    def status(self, config: BatchOcrConfig) -> dict[str, Any]:
        run_id = self._resolve_run_id(config)
        manifest = self._load_manifest(config.output_dir, run_id)
        batch_name = str(manifest.get("batch_job_name") or "").strip()
        if not batch_name:
            raise RuntimeError(f"Run {run_id} has not been submitted")
        client = self._client(config)
        try:
            job = client.get_batch(batch_name)
            state = GeminiBatchClient.batch_state(job)
            write_json(self._workspace(config.output_dir, run_id) / "job.json", {"run_id": run_id, "batch_job_name": batch_name, "job": job})
            self._usage_store(config).update_run_status(run_id, state, batch_name)
            return {"run_id": run_id, "batch_job_name": batch_name, "state": state, "job": job}
        finally:
            self._close_client(client)

    def collect(self, config: BatchOcrConfig) -> BatchCollectSummary:
        run_id = self._resolve_run_id(config)
        workspace = self._workspace(config.output_dir, run_id)
        manifest = self._load_manifest(config.output_dir, run_id)
        batch_name = str(manifest.get("batch_job_name") or "").strip()
        if not batch_name:
            raise RuntimeError(f"Run {run_id} has not been submitted")
        client = self._client(config)
        try:
            job = client.get_batch(batch_name)
            state = GeminiBatchClient.batch_state(job)
            if state != "JOB_STATE_SUCCEEDED" and not config.allow_partial:
                self._usage_store(config).update_run_status(run_id, state, batch_name)
                raise RuntimeError(f"Batch job {batch_name} is not collectable: {state}")

            result_file_name = GeminiBatchClient.result_file_name(job)
            if result_file_name:
                result_bytes = client.download_file(result_file_name)
                (workspace / "results.jsonl").write_bytes(result_bytes)
            elif not (workspace / "results.jsonl").exists():
                raise RuntimeError(f"Batch job {batch_name} has no result file")

            result_lines = (workspace / "results.jsonl").read_text(encoding="utf-8").splitlines()
            results_by_key = self.parse_result_lines(result_lines)
            summary = self._write_outputs_from_results(
                config=config,
                manifest=manifest,
                results_by_key=results_by_key,
                terminal_state=state,
            )
            manifest["status"] = summary.status
            manifest["updated_at"] = utc_now_iso()
            self._save_manifest(config.output_dir, run_id, manifest)
            return summary
        finally:
            self._close_client(client)

    def run(self, config: BatchOcrConfig, *, wait: bool = False) -> BatchCollectSummary | dict[str, Any]:
        manifest = self.prepare(config)
        if self._uploaded_request_count(manifest) <= 0:
            summary = self._prepare_noop_summary(manifest)
            self._usage_store(config).update_run_status(summary.run_id, summary.status)
            return summary
        submitted = self.submit(BatchOcrConfig(**{**asdict(config), "run_id": manifest["run_id"]}))
        if not wait:
            return submitted
        wait_config = BatchOcrConfig(**{**asdict(config), "run_id": manifest["run_id"]})
        while True:
            status = self.status(wait_config)
            state = status["state"]
            if state in TERMINAL_STATES:
                break
            time.sleep(max(1, config.poll_interval_seconds))
        return self.collect(wait_config)

    @staticmethod
    def parse_result_lines(lines: list[str]) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for raw_line in lines:
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as error:
                results[f"malformed:{len(results)}"] = {"error": f"Malformed JSONL line: {error}"}
                continue
            key = (
                payload.get("key")
                or payload.get("metadata", {}).get("key")
                or payload.get("request", {}).get("key")
            )
            if not isinstance(key, str) or not key:
                key = f"missing-key:{len(results)}"
            results[key] = payload
        return results

    @staticmethod
    def usage_from_response(
        response: dict[str, Any],
        *,
        input_cost_usd_per_1m_tokens: float,
        output_cost_usd_per_1m_tokens: float,
    ) -> UsageRecord:
        usage = response.get("usageMetadata") or response.get("usage_metadata") or {}
        input_tokens = GeminiBatchOcrService._usage_int(usage, "promptTokenCount", "prompt_token_count")
        candidate_output_tokens = GeminiBatchOcrService._usage_int(
            usage, "candidatesTokenCount", "candidates_token_count"
        )
        thoughts_tokens = GeminiBatchOcrService._usage_int(usage, "thoughtsTokenCount", "thoughts_token_count")
        output_tokens = candidate_output_tokens + thoughts_tokens
        total_tokens = GeminiBatchOcrService._usage_int(usage, "totalTokenCount", "total_token_count")
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens
        estimated_cost = (
            (input_tokens / 1_000_000.0) * max(0.0, input_cost_usd_per_1m_tokens)
            + (output_tokens / 1_000_000.0) * max(0.0, output_cost_usd_per_1m_tokens)
        )
        return UsageRecord(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=round(estimated_cost, 8),
        )

    @staticmethod
    def extract_text_from_response(response: dict[str, Any]) -> str:
        candidates = response.get("candidates", [])
        chunks: list[str] = []
        for candidate in candidates:
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunk for chunk in chunks if chunk)

    def _write_outputs_from_results(
        self,
        *,
        config: BatchOcrConfig,
        manifest: dict[str, Any],
        results_by_key: dict[str, dict[str, Any]],
        terminal_state: str,
    ) -> BatchCollectSummary:
        usage_store = self._usage_store(config)
        usage_store.initialize()
        pages_by_pdf: dict[str, list[PageExtractionResult]] = defaultdict(list)
        pdf_metadata: dict[str, dict[str, Any]] = {}
        failures: list[dict[str, Any]] = []

        for document in manifest.get("documents", []):
            pdf_path = str(document.get("pdf_path") or "")
            if not pdf_path:
                continue
            pdf_metadata[pdf_path] = {
                "pdf_stem": document.get("pdf_stem") or Path(pdf_path).stem,
                "total_pages": int(document.get("total_pages") or 0),
                "status": document.get("status"),
                "error": document.get("error"),
            }

        for page in manifest.get("pages", []):
            request_key = str(page.get("request_key") or "")
            pdf_path = str(page.get("pdf_path") or "")
            page_number = int(page.get("page_number") or 0)
            result_payload = results_by_key.get(request_key)
            status = "failed"
            error = None
            markdown = ""
            usage = UsageRecord()

            if page.get("status") != "uploaded":
                error = str(page.get("error") or "Page was not uploaded")
            elif result_payload is None:
                error = "Missing batch result for page"
            else:
                error_payload = result_payload.get("error") or result_payload.get("status")
                response = (
                    result_payload.get("response")
                    or result_payload.get("inlineResponse", {}).get("response")
                    or result_payload.get("inline_response", {}).get("response")
                    or result_payload
                )
                if error_payload and not response.get("candidates"):
                    error = json.dumps(error_payload, ensure_ascii=False)
                else:
                    usage = self.usage_from_response(
                        response,
                        input_cost_usd_per_1m_tokens=config.input_cost_usd_per_1m_tokens,
                        output_cost_usd_per_1m_tokens=config.output_cost_usd_per_1m_tokens,
                    )
                    markdown = normalize_model_markdown(self.extract_text_from_response(response)).strip()
                    if markdown:
                        status = "success"
                    else:
                        error = "Gemini batch response returned empty text or missing usage/content"

            usage_store.upsert_page_usage(
                run_id=str(manifest["run_id"]),
                request_key=request_key,
                pdf_path=pdf_path,
                page_number=page_number,
                status=status,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                estimated_cost_usd=usage.estimated_cost_usd,
                error=error,
            )
            if status != "success":
                failures.append({"request_key": request_key, "pdf_path": pdf_path, "page_number": page_number, "error": error})
            pages_by_pdf[pdf_path].append(
                PageExtractionResult(
                    page_number=page_number,
                    markdown=markdown,
                    draft_markdown=markdown or None,
                    status=status,
                    attempts=1,
                    error=error,
                    arabic_char_count=count_arabic_characters(markdown),
                )
            )

        self._write_failures(config.output_dir, str(manifest["run_id"]), failures)
        usage_store.rebuild_pdf_usage(str(manifest["run_id"]), pdf_metadata)
        total_processed_pages = 0
        total_failed_pages = 0
        success_pdfs = 0
        failed_pdfs = 0
        partial_pdfs = 0
        manifest_store = ManifestStore(config.output_dir)

        for pdf_path, metadata in pdf_metadata.items():
            if metadata.get("status") == "skipped_existing":
                continue
            total_pages = int(metadata.get("total_pages") or 0)
            page_results = sorted(pages_by_pdf.get(pdf_path, []), key=lambda item: item.page_number)
            pdf_usage = usage_store.get_pdf_usage(str(manifest["run_id"]), pdf_path) or {}
            if not page_results and metadata.get("status") == "invalid_pdf":
                result = DocumentExtractionResult(
                    pdf_path=Path(pdf_path),
                    md_path=config.output_dir / f"{safe_file_stem(Path(pdf_path).stem)}.md",
                    status="invalid_pdf",
                    total_pages=0,
                    processed_pages=0,
                    error=str(metadata.get("error") or "Invalid PDF"),
                )
                manifest_store.save_document(result)
                failed_pdfs += 1
                continue

            processed_pages = sum(1 for item in page_results if item.status == "success")
            failed_pages = max(0, total_pages - processed_pages)
            total_processed_pages += processed_pages
            total_failed_pages += failed_pages
            status = "success"
            if processed_pages == 0 and total_pages > 0:
                status = "failed"
                failed_pdfs += 1
            elif failed_pages > 0:
                status = "partial"
                partial_pdfs += 1
            else:
                success_pdfs += 1

            result = DocumentExtractionResult(
                pdf_path=Path(pdf_path),
                md_path=config.output_dir / f"{safe_file_stem(Path(pdf_path).stem)}.md",
                status=status,
                total_pages=total_pages,
                processed_pages=processed_pages,
                page_results=page_results,
                input_tokens=int(pdf_usage.get("input_tokens") or 0),
                output_tokens=int(pdf_usage.get("output_tokens") or 0),
                total_tokens=int(pdf_usage.get("total_tokens") or 0),
                estimated_cost_usd=float(pdf_usage.get("estimated_cost_usd") or 0.0),
            )
            markdown_doc = PdfOcrService._compose_document_markdown(pdf_path=Path(pdf_path), result=result)
            if result.md_path and (config.overwrite or not result.md_path.exists()):
                write_text(result.md_path, markdown_doc)
            manifest_store.save_document(result)

        final_status = "collected" if terminal_state == "JOB_STATE_SUCCEEDED" else terminal_state
        totals = usage_store.rebuild_run_totals(str(manifest["run_id"]), final_status)
        return BatchCollectSummary(
            run_id=str(manifest["run_id"]),
            status=final_status,
            total_pdfs=int(totals.get("total_pdfs") or 0),
            success_pdfs=success_pdfs,
            failed_pdfs=failed_pdfs,
            partial_pdfs=partial_pdfs,
            total_pages=int(totals.get("total_pages") or 0),
            processed_pages=total_processed_pages,
            failed_pages=total_failed_pages,
            input_tokens=int(totals.get("input_tokens") or 0),
            output_tokens=int(totals.get("output_tokens") or 0),
            total_tokens=int(totals.get("total_tokens") or 0),
            estimated_cost_usd=float(totals.get("estimated_cost_usd") or 0.0),
        )

    def _write_requests_jsonl(self, *, manifest: dict[str, Any], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for page in manifest.get("pages", []):
                if page.get("status") != "uploaded":
                    continue
                prompt = build_ocr_prompt(
                    pdf_name=Path(str(page["pdf_path"])).name,
                    page_number=int(page["page_number"]),
                    total_pages=int(page["total_pages"]),
                )
                payload = {
                    "key": page["request_key"],
                    "request": {
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "file_data": {
                                            "mime_type": "image/png",
                                            "file_uri": page["file_uri"],
                                        }
                                    },
                                    {"text": prompt},
                                ],
                            }
                        ],
                        "generationConfig": {"temperature": 0, "topP": 0.95},
                    },
                }
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    @staticmethod
    def _request_key(pdf_path: Path, page_number: int) -> str:
        return f"{safe_file_stem(pdf_path.stem)}__page_{page_number:04d}"

    @staticmethod
    def _usage_int(usage: dict[str, Any], *keys: str) -> int:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
        return 0

    def _client(self, config: BatchOcrConfig) -> GeminiBatchClient:
        if self.client is not None:
            return self.client
        return GeminiBatchClient(
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.request_timeout_seconds,
        )

    @staticmethod
    def _close_client(client: GeminiBatchClient | Any) -> None:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _usage_store(config: BatchOcrConfig) -> GeminiUsageStore:
        return GeminiUsageStore(config.usage_db_path or (config.output_dir / "gemini_usage.sqlite3"))

    @staticmethod
    def _workspace(output_dir: Path, run_id: str) -> Path:
        return output_dir / "_batch" / run_id

    @staticmethod
    def _new_run_id() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    @classmethod
    def _save_manifest(cls, output_dir: Path, run_id: str, manifest: dict[str, Any]) -> None:
        write_json(cls._workspace(output_dir, run_id) / "batch_manifest.json", manifest)

    @classmethod
    def _load_manifest(cls, output_dir: Path, run_id: str) -> dict[str, Any]:
        path = cls._workspace(output_dir, run_id) / "batch_manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_latest_run_id(output_dir: Path, run_id: str) -> None:
        write_text(output_dir / "_batch" / "latest_run_id", run_id)

    @staticmethod
    def _latest_run_id(output_dir: Path) -> str:
        path = output_dir / "_batch" / "latest_run_id"
        if not path.exists():
            raise RuntimeError(f"No batch run id provided and no latest run exists at {path}")
        return path.read_text(encoding="utf-8").strip()

    def _resolve_run_id(self, config: BatchOcrConfig) -> str:
        return config.run_id or self._latest_run_id(config.output_dir)

    def _write_failures(self, output_dir: Path, run_id: str, failures: list[dict[str, Any]]) -> None:
        path = self._workspace(output_dir, run_id) / "failures.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for failure in failures:
                handle.write(json.dumps(failure, ensure_ascii=False, sort_keys=True) + "\n")

    @staticmethod
    def _uploaded_request_count(manifest: dict[str, Any]) -> int:
        return sum(1 for page in manifest.get("pages", []) if page.get("status") == "uploaded")

    @staticmethod
    def _no_uploaded_pages_error(manifest: dict[str, Any]) -> str:
        statuses = defaultdict(int)
        for document in manifest.get("documents", []):
            statuses[str(document.get("status") or "unknown")] += 1
        if statuses and set(statuses) == {"skipped_existing"}:
            return (
                "No uploaded pages are available for batch submission: all selected PDFs were "
                "skipped because Markdown files already exist. Re-run with --overwrite to force reprocessing."
            )
        status_summary = ", ".join(f"{key}={value}" for key, value in sorted(statuses.items())) or "none"
        return (
            "No uploaded pages are available for batch submission. "
            f"Document statuses: {status_summary}. "
            "Use --overwrite to reprocess already extracted PDFs."
        )

    @staticmethod
    def _prepare_noop_summary(manifest: dict[str, Any]) -> BatchCollectSummary:
        statuses = [str(doc.get("status") or "") for doc in manifest.get("documents", [])]
        run_id = str(manifest.get("run_id") or "")
        if statuses and all(status == "skipped_existing" for status in statuses):
            status = "skipped_existing"
        elif statuses and all(status == "invalid_pdf" for status in statuses):
            status = "invalid_pdf"
        else:
            status = "no_uploaded_pages"
        return BatchCollectSummary(
            run_id=run_id,
            status=status,
            total_pdfs=len(manifest.get("documents", [])),
            success_pdfs=0,
            failed_pdfs=0,
            partial_pdfs=0,
            total_pages=0,
            processed_pages=0,
            failed_pages=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0.0,
        )
