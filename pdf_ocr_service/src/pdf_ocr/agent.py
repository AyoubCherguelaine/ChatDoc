from __future__ import annotations

import logging
import time

from arabic_pdf_md_agent.base.schemas import DocumentExtractionResult, ExtractionConfig, RunSummary
from arabic_pdf_md_agent.base.utils import resolve_pdf_inputs
from arabic_pdf_md_agent.pdf_ocr.db.manifest_store import ManifestStore
from arabic_pdf_md_agent.pdf_ocr.service import PdfOcrService
from arabic_pdf_md_agent.pdf_ocr.tools.gemini_client import GeminiVisionClient
from arabic_pdf_md_agent.pdf_ocr.tools.pdf_renderer import PdfRenderer

logger = logging.getLogger(__name__)


class PdfOcrDomainAgent:
    """Domain agent that scans PDFs and delegates extraction per document."""

    def run(self, config: ExtractionConfig) -> tuple[list[DocumentExtractionResult], RunSummary]:
        run_started = time.monotonic()
        pdf_paths = resolve_pdf_inputs(
            input_pdf=config.input_pdf,
            input_dir=config.input_dir,
            include_glob=config.include_glob,
            recursive=config.recursive,
        )

        summary = RunSummary(total_pdfs=len(pdf_paths))
        results: list[DocumentExtractionResult] = []
        manifest_store = ManifestStore(config.output_dir)
        usage_log_path = None
        if config.enable_usage_json_log:
            usage_log_path = config.usage_log_path or (config.output_dir / "gemini_usage.jsonl")

        gemini_client = GeminiVisionClient(
            api_key=config.api_key,
            model=config.model,
            timeout_seconds=config.request_timeout_seconds,
            max_retries=config.gemini_client_max_retries,
            retry_backoff_seconds=config.gemini_client_retry_backoff_seconds,
            usage_log_path=usage_log_path,
            input_cost_usd_per_1m_tokens=config.input_cost_usd_per_1m_tokens,
            output_cost_usd_per_1m_tokens=config.output_cost_usd_per_1m_tokens,
        )
        service = PdfOcrService(renderer=PdfRenderer(), gemini_client=gemini_client)

        for pdf_path in pdf_paths:
            logger.info("Processing PDF: %s", pdf_path.name)
            pdf_started = time.monotonic()
            usage_before = gemini_client.usage_summary()
            result = service.extract_document(pdf_path=pdf_path, config=config)
            usage_after = gemini_client.usage_summary()
            result.elapsed_ms = int((time.monotonic() - pdf_started) * 1000)
            result.model_calls = int(usage_after["model_calls"]) - int(usage_before["model_calls"])
            result.input_tokens = int(usage_after["input_tokens"]) - int(usage_before["input_tokens"])
            result.output_tokens = int(usage_after["output_tokens"]) - int(usage_before["output_tokens"])
            result.total_tokens = int(usage_after["total_tokens"]) - int(usage_before["total_tokens"])
            result.estimated_cost_usd = round(
                max(0.0, float(usage_after["estimated_cost_usd"]) - float(usage_before["estimated_cost_usd"])),
                8,
            )
            results.append(result)
            manifest_store.save_document(result)
            logger.info(
                "Finished PDF: %s status=%s elapsed_ms=%s model_calls=%s tokens=%s/%s cost_usd=%.6f",
                pdf_path.name,
                result.status,
                result.elapsed_ms,
                result.model_calls,
                result.input_tokens,
                result.output_tokens,
                result.estimated_cost_usd,
            )

            summary.total_pages += result.total_pages
            summary.processed_pages += result.processed_pages
            if result.status == "success":
                summary.success_pdfs += 1
            elif result.status == "skipped_existing":
                summary.skipped_pdfs += 1
            else:
                summary.failed_pdfs += 1
        usage = gemini_client.usage_summary()
        summary.model_calls = int(usage["model_calls"])
        summary.input_tokens = int(usage["input_tokens"])
        summary.output_tokens = int(usage["output_tokens"])
        summary.total_tokens = int(usage["total_tokens"])
        summary.estimated_cost_usd = float(usage["estimated_cost_usd"])
        summary.elapsed_ms = int((time.monotonic() - run_started) * 1000)

        manifest_store.save_summary(summary)
        return results, summary
