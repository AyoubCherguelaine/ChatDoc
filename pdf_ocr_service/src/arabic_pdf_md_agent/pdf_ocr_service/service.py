from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from arabic_pdf_md_agent.base.errors import PdfOcrError, PdfOcrProcessingError
from arabic_pdf_md_agent.base.prompts import normalize_model_markdown
from arabic_pdf_md_agent.base.schemas import DocumentExtractionResult, ExtractionConfig, PageExtractionResult
from arabic_pdf_md_agent.base.utils import (
    chunk_ranges,
    count_arabic_characters,
    is_probably_pdf,
    safe_file_stem,
    write_text,
)
from arabic_pdf_md_agent.pdf_ocr_service.prompts import (
    build_document_prompt,
    build_document_review_prompt,
    build_ocr_prompt,
    build_review_prompt,
)
from arabic_pdf_md_agent.pdf_ocr_service.semantic import (
    build_semantic_prompt,
    has_semantic_output,
    parse_semantic_page,
    previous_block,
    save_semantic_result,
)
from arabic_pdf_md_agent.pdf_ocr_service.tools.gemini_client import GeminiVisionClient
from arabic_pdf_md_agent.pdf_ocr_service.tools.pdf_chunker import PdfChunker
from arabic_pdf_md_agent.pdf_ocr_service.tools.pdf_renderer import PdfRenderer

logger = logging.getLogger(__name__)
_PAGE_MARKER_RE = re.compile(r"<!--\s*PAGE:\s*(\d+)\s*-->")
_ARTICLE_REF_RE = re.compile(r"(?:المادة|البند|الفقرة|الفصل|الباب)\s+[\w\d\u0600-\u06FF()]+")
_DIGIT_RE = re.compile(r"[\d\u0660-\u0669]")


class PdfOcrService:
    """Extract semantic blocks and verbatim OCR, with a legacy Markdown pipeline."""

    def __init__(
        self,
        renderer: PdfRenderer,
        gemini_client: GeminiVisionClient,
        chunker: PdfChunker | None = None,
    ) -> None:
        self.renderer = renderer
        self.gemini_client = gemini_client
        self.chunker = chunker or PdfChunker()

    def extract_document(self, pdf_path: Path, config: ExtractionConfig) -> DocumentExtractionResult:
        md_path = config.output_dir / f"{safe_file_stem(pdf_path.stem)}.md"
        result = DocumentExtractionResult(pdf_path=pdf_path, md_path=md_path)

        config.output_dir.mkdir(parents=True, exist_ok=True)

        if md_path.exists() and not config.overwrite and (not config.semantic_blocks or has_semantic_output(md_path)):
            result.status = "skipped_existing"
            return result

        if not pdf_path.exists():
            result.status = "failed"
            result.error = f"PDF does not exist: {pdf_path}"
            return result
        if not pdf_path.is_file():
            result.status = "failed"
            result.error = f"PDF path is not a file: {pdf_path}"
            return result

        if not is_probably_pdf(pdf_path):
            result.status = "invalid_pdf"
            result.error = "File does not have a valid %PDF header signature"
            return result

        try:
            try:
                total_pages = self.renderer.page_count(pdf_path)
            except Exception as error:
                raise PdfOcrProcessingError(f"Failed to inspect PDF {pdf_path}: {error}") from error

            page_limit = min(total_pages, config.max_pages_per_pdf) if config.max_pages_per_pdf else total_pages
            result.total_pages = page_limit
            if page_limit <= 0:
                result.status = "failed"
                result.error = "PDF has no pages"
                return result

            document_first_error: str | None = None
            document_results: list[PageExtractionResult] = []
            if config.semantic_blocks:
                document_results = self._extract_semantic_pages(pdf_path, page_limit, config)
            elif config.gemini_document_first:
                try:
                    document_results = self._extract_document_first_chunked(
                        pdf_path=pdf_path,
                        total_pages=total_pages,
                        page_limit=page_limit,
                        config=config,
                    )
                    logger.info("Gemini document-first succeeded for %s", pdf_path.name)
                except Exception as error:  # pragma: no cover - external API behavior
                    document_first_error = str(error)
                    logger.warning(
                        "Gemini document-first failed for %s, moving to page fallback: %s",
                        pdf_path.name,
                        error,
                    )

            fallback_targets = set() if config.semantic_blocks else self._pages_needing_fallback(
                page_results=document_results,
                page_limit=page_limit,
                config=config,
            )
            fallback_results: list[PageExtractionResult] = []
            if fallback_targets:
                fallback_results = self._extract_with_page_images(
                    pdf_path=pdf_path,
                    page_limit=page_limit,
                    target_pages=fallback_targets,
                    config=config,
                )

            merged = self._merge_results(
                document_results=document_results,
                fallback_results=fallback_results,
                page_limit=page_limit,
                config=config,
            )
            result.page_results = merged
            result.processed_pages = sum(1 for page in merged if page.status == "success")

            if result.processed_pages == result.total_pages:
                result.status = "success"
            elif result.processed_pages > 0:
                result.status = "partial"
            else:
                result.status = "failed"

            if document_first_error and result.status != "success":
                result.error = f"Document-first error: {document_first_error}"
            if result.error is None and result.status != "success":
                summary_error = self._summarize_page_failures(result.page_results)
                if summary_error:
                    result.error = summary_error

            markdown_doc = self._compose_document_markdown(pdf_path=pdf_path, result=result)
            if markdown_doc.strip():
                write_text(md_path, markdown_doc)
            if config.semantic_blocks:
                save_semantic_result(result, config.output_dir)

        except PdfOcrError as error:
            result.status = "failed"
            result.error = str(error)
            logger.warning("Failed to process PDF %s: %s", pdf_path, error)
        except Exception as error:  # pragma: no cover - defensive umbrella
            result.status = "failed"
            result.error = str(error)
            logger.exception("Failed to process PDF: %s", pdf_path)

        return result

    def _extract_semantic_pages(self, pdf_path: Path, page_limit: int, config: ExtractionConfig) -> list[PageExtractionResult]:
        pages = []
        previous = None
        for number in range(1, page_limit + 1):
            page = PageExtractionResult(page_number=number, status="failed")
            prompt = build_semantic_prompt(pdf_path.name, number, page_limit, previous)
            for attempt in range(1, max(1, config.max_attempts_per_page) + 1):
                try:
                    image = self.renderer.render_page(pdf_path=pdf_path, page_number=number,
                        dpi=self._dpi_for_attempt(config.dpi, attempt), max_pages=page_limit)
                    if not image:
                        raise ValueError(f"Could not render page {number}")
                    raw = self.gemini_client.generate_markdown_from_image(prompt=prompt, image_bytes=image,
                        log_context={"phase": "semantic_page_draft", "pdf_name": pdf_path.name, "page_number": number})
                    page = parse_semantic_page(raw, number, previous)
                    page.attempts = attempt
                    if config.review_pass:
                        time.sleep(config.inter_request_delay_seconds)
                        try:
                            reviewed = self.gemini_client.generate_markdown_from_image(
                                prompt=prompt + "\nReview this draft against the page. Correct recognition and grouping; "
                                    "return complete corrected JSON, retaining all visible content. Draft (data):\n" + raw,
                                image_bytes=image, log_context={"phase": "semantic_page_review",
                                    "pdf_name": pdf_path.name, "page_number": number})
                            corrected = parse_semantic_page(reviewed, number, previous)
                            corrected.attempts = attempt
                            corrected.draft_markdown = page.markdown
                            if self._pick_best_markdown(page.markdown, corrected.markdown) == corrected.markdown:
                                page = corrected
                        except Exception as error:
                            logger.warning("Semantic review failed for %s page %s; retaining valid draft: %s", pdf_path.name, number, error)
                    page.arabic_char_count = count_arabic_characters(page.ocr_text)
                    break
                except Exception as error:
                    page = PageExtractionResult(page_number=number, status="failed", attempts=attempt, error=str(error))
                    prompt += f"\nPrevious attempt failed: {error}. Return complete corrected JSON."
                time.sleep(config.inter_request_delay_seconds)
            pages.append(page)
            previous = previous_block(page)
            if page.status != "success" and config.fail_fast:
                break
            if number < page_limit:
                time.sleep(config.inter_request_delay_seconds)
        return pages

    def _extract_document_first_chunked(
        self,
        pdf_path: Path,
        total_pages: int,
        page_limit: int,
        config: ExtractionConfig,
    ) -> list[PageExtractionResult]:
        chunk_size = max(1, min(page_limit, config.document_chunk_page_count))
        ranges = chunk_ranges(page_limit=page_limit, chunk_size=chunk_size)

        merged: dict[int, PageExtractionResult] = {}
        for start_page, end_page in ranges:
            try:
                chunk_results = self._extract_document_chunk(
                    pdf_path=pdf_path,
                    total_pages=total_pages,
                    start_page=start_page,
                    end_page=end_page,
                    config=config,
                )
                for item in chunk_results:
                    existing = merged.get(item.page_number)
                    if self._prefer_replacement(item, existing, config):
                        merged[item.page_number] = item
            except Exception as chunk_error:  # pragma: no cover - external API behavior
                logger.warning(
                    "Document-first chunk failed for %s pages %s-%s: %s. Falling back to page-image OCR.",
                    pdf_path.name,
                    start_page,
                    end_page,
                    chunk_error,
                )
                try:
                    fallback_results = self._extract_with_page_images(
                        pdf_path=pdf_path,
                        page_limit=page_limit,
                        target_pages=set(range(start_page, end_page + 1)),
                        config=config,
                    )
                except Exception as fallback_error:  # pragma: no cover - external API behavior
                    logger.warning(
                        "Page-image fallback also failed for %s pages %s-%s after document-first error %s: %s",
                        pdf_path.name,
                        start_page,
                        end_page,
                        chunk_error,
                        fallback_error,
                    )
                    fallback_results = []

                if fallback_results:
                    for item in fallback_results:
                        existing = merged.get(item.page_number)
                        if self._prefer_replacement(item, existing, config):
                            merged[item.page_number] = item
                    continue

                for page_number in range(start_page, end_page + 1):
                    existing = merged.get(page_number)
                    fallback_placeholder = PageExtractionResult(
                        page_number=page_number,
                        status="failed",
                        attempts=1,
                        error=f"Document-first chunk failed: {chunk_error}",
                    )
                    if self._prefer_replacement(fallback_placeholder, existing, config):
                        merged[page_number] = fallback_placeholder

        if not merged:
            raise ValueError("Document-first produced no page results")

        return sorted(merged.values(), key=lambda item: item.page_number)

    def _extract_document_chunk(
        self,
        pdf_path: Path,
        total_pages: int,
        start_page: int,
        end_page: int,
        config: ExtractionConfig,
    ) -> list[PageExtractionResult]:
        chunk_bytes = self.chunker.make_chunk_bytes(
            pdf_path=pdf_path,
            start_page=start_page,
            end_page=end_page,
        )

        draft_prompt = build_document_prompt(
            pdf_name=pdf_path.name,
            total_pages=total_pages,
            page_start=start_page,
            page_end=end_page,
        )
        draft = self.gemini_client.generate_markdown_from_pdf(
            prompt=draft_prompt,
            pdf_bytes=chunk_bytes,
            log_context={
                "phase": "document_first_draft",
                "pdf_name": pdf_path.name,
                "page_start": start_page,
                "page_end": end_page,
            },
        )
        draft = normalize_model_markdown(draft)
        draft = draft.strip()
        if not draft:
            raise ValueError("Gemini document-first returned empty Markdown")
        final_markdown = draft

        if config.review_pass:
            time.sleep(config.inter_request_delay_seconds)
            try:
                review_prompt = build_document_review_prompt(
                    draft_markdown=draft,
                    page_start=start_page,
                    page_end=end_page,
                )
                reviewed = self.gemini_client.generate_markdown_from_pdf(
                    prompt=review_prompt,
                    pdf_bytes=chunk_bytes,
                    log_context={
                        "phase": "document_first_review",
                        "pdf_name": pdf_path.name,
                        "page_start": start_page,
                        "page_end": end_page,
                    },
                )
                reviewed = normalize_model_markdown(reviewed)
                final_markdown = self._pick_best_markdown(draft=draft, reviewed=reviewed)
            except Exception as review_error:  # pragma: no cover - external API behavior
                logger.warning(
                    "Document review failed for %s pages %s-%s, keeping draft: %s",
                    pdf_path.name,
                    start_page,
                    end_page,
                    review_error,
                )

        expected_pages = set(range(start_page, end_page + 1))
        return self._split_document_markdown_to_pages(
            markdown_text=final_markdown,
            expected_pages=expected_pages,
        )

    def _extract_with_page_images(
        self,
        pdf_path: Path,
        page_limit: int,
        target_pages: set[int],
        config: ExtractionConfig,
    ) -> list[PageExtractionResult]:
        if not target_pages:
            return []

        page_results: list[PageExtractionResult] = []
        rendered_pages = self.renderer.iter_selected_pages(
            pdf_path=pdf_path,
            dpi=config.dpi,
            page_numbers=target_pages,
            max_pages=page_limit,
        )
        rendered_by_page = {page_number: image_bytes for page_number, image_bytes in rendered_pages}

        for page_number in sorted(target_pages):
            image_bytes = rendered_by_page.get(page_number)
            if image_bytes is None:
                page_results.append(
                    PageExtractionResult(
                        page_number=page_number,
                        status="failed",
                        attempts=1,
                        error="Fallback did not render this page",
                    )
                )
                if config.fail_fast:
                    break
                continue

            page_result = self._extract_page(
                pdf_path=pdf_path,
                page_number=page_number,
                total_pages=page_limit,
                page_limit=page_limit,
                image_bytes=image_bytes,
                config=config,
            )
            page_results.append(page_result)

            if page_result.status != "success" and config.fail_fast:
                break

        return sorted(page_results, key=lambda item: item.page_number)

    def _extract_page(
        self,
        pdf_path: Path,
        page_number: int,
        total_pages: int,
        page_limit: int,
        image_bytes: bytes,
        config: ExtractionConfig,
    ) -> PageExtractionResult:
        page_result = PageExtractionResult(page_number=page_number)
        last_error: Exception | None = None
        max_attempts = max(1, config.max_attempts_per_page)

        for attempt in range(1, max_attempts + 1):
            page_result.attempts = attempt
            attempt_image = image_bytes
            attempt_dpi = self._dpi_for_attempt(base_dpi=config.dpi, attempt=attempt)
            if attempt > 1:
                rerendered = self.renderer.render_page(
                    pdf_path=pdf_path,
                    page_number=page_number,
                    dpi=attempt_dpi,
                    max_pages=page_limit,
                )
                if rerendered:
                    attempt_image = rerendered
                    logger.info(
                        "Retrying OCR for %s page %s using rerendered image at %s DPI (attempt %s/%s)",
                        pdf_path.name,
                        page_number,
                        attempt_dpi,
                        attempt,
                        max_attempts,
                    )
            try:
                draft_prompt = build_ocr_prompt(
                    pdf_name=pdf_path.name,
                    page_number=page_number,
                    total_pages=total_pages,
                )
                draft = self.gemini_client.generate_markdown_from_image(
                    prompt=draft_prompt,
                    image_bytes=attempt_image,
                    log_context={
                        "phase": "page_image_draft",
                        "pdf_name": pdf_path.name,
                        "page_number": page_number,
                    },
                )
                draft = normalize_model_markdown(draft)
                draft = draft.strip()
                if not draft:
                    raise ValueError("Model returned empty Markdown")
                final_markdown = draft

                if config.review_pass:
                    time.sleep(config.inter_request_delay_seconds)
                    try:
                        review_prompt = build_review_prompt(
                            draft_markdown=draft,
                            page_number=page_number,
                            total_pages=total_pages,
                        )
                        reviewed = self.gemini_client.generate_markdown_from_image(
                            prompt=review_prompt,
                            image_bytes=attempt_image,
                            log_context={
                                "phase": "page_image_review",
                                "pdf_name": pdf_path.name,
                                "page_number": page_number,
                            },
                        )
                        reviewed = normalize_model_markdown(reviewed)
                        final_markdown = self._pick_best_markdown(draft=draft, reviewed=reviewed)
                    except Exception as review_error:  # pragma: no cover - external API behavior
                        logger.warning(
                            "Review pass failed for %s page %s attempt %s/%s, keeping draft: %s",
                            pdf_path.name,
                            page_number,
                            attempt,
                            max_attempts,
                            review_error,
                        )

                page_result.draft_markdown = draft
                page_result.markdown = final_markdown.strip()
                page_result.arabic_char_count = count_arabic_characters(final_markdown)
                page_result.status = "success"
                return page_result
            except Exception as error:  # pragma: no cover - external API behavior
                last_error = error
                logger.warning(
                    "Page OCR failed for %s page %s attempt %s/%s: %s",
                    pdf_path.name,
                    page_number,
                    attempt,
                    max_attempts,
                    error,
                )
                if attempt < max_attempts:
                    time.sleep(max(config.inter_request_delay_seconds, 0.5) * attempt)

        rescue_result = self._extract_page_from_single_page_pdf(
            pdf_path=pdf_path,
            page_number=page_number,
            total_pages=total_pages,
            config=config,
        )
        if rescue_result is not None:
            page_result.attempts += 1
            page_result.draft_markdown = rescue_result
            page_result.markdown = rescue_result
            page_result.arabic_char_count = count_arabic_characters(rescue_result)
            page_result.status = "success"
            logger.info(
                "Recovered OCR for %s page %s using single-page PDF rescue",
                pdf_path.name,
                page_number,
            )
            return page_result

        page_result.status = "failed"
        page_result.error = str(last_error) if last_error else "Unknown OCR failure"
        return page_result

    def _extract_page_from_single_page_pdf(
        self,
        pdf_path: Path,
        page_number: int,
        total_pages: int,
        config: ExtractionConfig,
    ) -> str | None:
        try:
            page_pdf_bytes = self.chunker.make_chunk_bytes(
                pdf_path=pdf_path,
                start_page=page_number,
                end_page=page_number,
            )
            draft_prompt = build_document_prompt(
                pdf_name=pdf_path.name,
                total_pages=total_pages,
                page_start=page_number,
                page_end=page_number,
            )
            draft = self.gemini_client.generate_markdown_from_pdf(
                prompt=draft_prompt,
                pdf_bytes=page_pdf_bytes,
                log_context={
                    "phase": "single_page_pdf_rescue_draft",
                    "pdf_name": pdf_path.name,
                    "page_number": page_number,
                },
            )
            draft = normalize_model_markdown(draft).strip()
            if not draft:
                return None

            final_markdown = draft
            if config.review_pass:
                time.sleep(config.inter_request_delay_seconds)
                try:
                    review_prompt = build_document_review_prompt(
                        draft_markdown=draft,
                        page_start=page_number,
                        page_end=page_number,
                    )
                    reviewed = self.gemini_client.generate_markdown_from_pdf(
                        prompt=review_prompt,
                        pdf_bytes=page_pdf_bytes,
                        log_context={
                            "phase": "single_page_pdf_rescue_review",
                            "pdf_name": pdf_path.name,
                            "page_number": page_number,
                        },
                    )
                    reviewed = normalize_model_markdown(reviewed)
                    final_markdown = self._pick_best_markdown(draft=draft, reviewed=reviewed).strip()
                except Exception as review_error:  # pragma: no cover - external API behavior
                    logger.warning(
                        "Single-page PDF review failed for %s page %s, keeping draft: %s",
                        pdf_path.name,
                        page_number,
                        review_error,
                    )

            if not final_markdown:
                return None

            parsed = self._split_document_markdown_to_pages(
                markdown_text=final_markdown,
                expected_pages={page_number},
            )
            for item in parsed:
                if item.page_number == page_number and item.status == "success" and item.markdown.strip():
                    return item.markdown.strip()
            return final_markdown
        except Exception as error:  # pragma: no cover - external API behavior
            logger.warning(
                "Single-page PDF rescue failed for %s page %s: %s",
                pdf_path.name,
                page_number,
                error,
            )
            return None

    @staticmethod
    def _dpi_for_attempt(base_dpi: int, attempt: int) -> int:
        safe_base = max(base_dpi, 72)
        if attempt <= 1:
            return safe_base
        max_dpi = max(300, safe_base * 2)
        return min(max_dpi, safe_base + ((attempt - 1) * 50))

    def _split_document_markdown_to_pages(
        self,
        markdown_text: str,
        expected_pages: set[int],
    ) -> list[PageExtractionResult]:
        markers = list(_PAGE_MARKER_RE.finditer(markdown_text))
        expected_sorted = sorted(expected_pages)
        if not expected_sorted:
            return []

        results: list[PageExtractionResult] = []
        used_pages: set[int] = set()

        if not markers:
            body = markdown_text.strip()
            if not body:
                raise ValueError("Document output is empty")
            first_page = expected_sorted[0]
            used_pages.add(first_page)
            results.append(
                PageExtractionResult(
                    page_number=first_page,
                    markdown=body,
                    draft_markdown=body,
                    status="success",
                    attempts=1,
                    arabic_char_count=count_arabic_characters(body),
                )
            )
        else:
            for idx, marker in enumerate(markers):
                page_number = int(marker.group(1))
                if page_number not in expected_pages or page_number in used_pages:
                    continue

                start = marker.end()
                end = markers[idx + 1].start() if idx + 1 < len(markers) else len(markdown_text)
                body = markdown_text[start:end].strip()
                if not body:
                    continue

                used_pages.add(page_number)
                results.append(
                    PageExtractionResult(
                        page_number=page_number,
                        markdown=body,
                        draft_markdown=body,
                        status="success",
                        attempts=1,
                        arabic_char_count=count_arabic_characters(body),
                    )
                )

        for page_number in expected_sorted:
            if page_number in used_pages:
                continue
            results.append(
                PageExtractionResult(
                    page_number=page_number,
                    status="failed",
                    attempts=1,
                    error="Document output missing this page marker or page content",
                )
            )

        return sorted(results, key=lambda item: item.page_number)

    def _pages_needing_fallback(
        self,
        page_results: list[PageExtractionResult],
        page_limit: int,
        config: ExtractionConfig,
    ) -> set[int]:
        if not page_results:
            return set(range(1, page_limit + 1))

        by_page = {item.page_number: item for item in page_results}
        targets: set[int] = set()

        for page_number in range(1, page_limit + 1):
            item = by_page.get(page_number)
            if item is None:
                targets.add(page_number)
                continue
            if item.status != "success":
                targets.add(page_number)
                continue
            if config.prefer_fallback_for_weak_pages and self._is_weak_extraction(item, config):
                targets.add(page_number)

        return targets

    def _merge_results(
        self,
        document_results: list[PageExtractionResult],
        fallback_results: list[PageExtractionResult],
        page_limit: int,
        config: ExtractionConfig,
    ) -> list[PageExtractionResult]:
        by_page: dict[int, PageExtractionResult] = {}

        for item in document_results:
            if not (1 <= item.page_number <= page_limit):
                continue
            existing = by_page.get(item.page_number)
            if self._prefer_replacement(item, existing, config):
                by_page[item.page_number] = item

        for item in fallback_results:
            if not (1 <= item.page_number <= page_limit):
                continue
            existing = by_page.get(item.page_number)
            if self._prefer_replacement(item, existing, config):
                by_page[item.page_number] = item

        merged: list[PageExtractionResult] = []
        for page_number in range(1, page_limit + 1):
            page_item = by_page.get(page_number)
            if page_item is None:
                page_item = PageExtractionResult(
                    page_number=page_number,
                    status="failed",
                    attempts=1,
                    error="No output for this page",
                )
            merged.append(page_item)

        return merged

    @staticmethod
    def _summarize_page_failures(page_results: list[PageExtractionResult], *, limit: int = 3) -> str | None:
        failures = [item for item in page_results if item.status != "success"]
        if not failures:
            return None

        pieces: list[str] = []
        for item in failures[:limit]:
            reason = item.error or item.status
            pieces.append(f"page {item.page_number}: {reason}")
        if len(failures) > limit:
            pieces.append(f"+{len(failures) - limit} more")
        return "; ".join(pieces)

    def _prefer_replacement(
        self,
        new_item: PageExtractionResult,
        current_item: PageExtractionResult | None,
        config: ExtractionConfig,
    ) -> bool:
        if current_item is None:
            return True

        if new_item.status == "success" and current_item.status != "success":
            return True
        if new_item.status != "success" and current_item.status == "success":
            return False

        if new_item.status != "success" and current_item.status != "success":
            return bool(new_item.error and not current_item.error)

        if not config.prefer_fallback_for_weak_pages:
            return False

        new_score = self._page_quality_score(new_item)
        current_score = self._page_quality_score(current_item)
        return new_score > (current_score * 1.05)

    @staticmethod
    def _is_weak_extraction(item: PageExtractionResult, config: ExtractionConfig) -> bool:
        body = item.markdown.strip()
        if item.arabic_char_count < config.min_page_arabic_chars:
            return True
        if body in {"[لا يوجد نص مقروء في هذه الصفحة].", "[لا يوجد نص مقروء في هذه الصفحة]"}:
            return True
        if body.count("[غير واضح]") >= 3:
            return True
        return False

    @staticmethod
    def _page_quality_score(item: PageExtractionResult) -> float:
        body = item.markdown.strip()
        structure_score = 0.0
        structure_score += len(_ARTICLE_REF_RE.findall(body)) * 30.0
        structure_score += len(_DIGIT_RE.findall(body)) * 3.0
        structure_score += body.count("|") * 4.0
        structure_score += body.count("\n") * 1.5
        unreadable_penalty = body.count("[غير واضح]") * 40.0
        return (item.arabic_char_count * 4.0) + float(len(body)) + structure_score - unreadable_penalty

    @staticmethod
    def _has_full_success(page_results: list[PageExtractionResult], page_limit: int) -> bool:
        if not page_results:
            return False
        by_page = {item.page_number: item for item in page_results}
        for page_number in range(1, page_limit + 1):
            page_item = by_page.get(page_number)
            if page_item is None or page_item.status != "success":
                return False
        return True

    @staticmethod
    def _pick_best_markdown(draft: str, reviewed: str) -> str:
        draft_clean = draft.strip()
        reviewed_clean = reviewed.strip()
        if not reviewed_clean:
            return draft_clean
        if PdfOcrService._looks_like_non_transcription(reviewed_clean):
            return draft_clean
        if PdfOcrService._lost_page_markers(draft_clean, reviewed_clean):
            return draft_clean
        draft_arabic = count_arabic_characters(draft_clean)
        reviewed_arabic = count_arabic_characters(reviewed_clean)
        if draft_arabic >= 40 and reviewed_arabic < draft_arabic * 0.75:
            return draft_clean
        draft_score = PdfOcrService._markdown_quality_score(draft_clean)
        reviewed_score = PdfOcrService._markdown_quality_score(reviewed_clean)
        if reviewed_score < draft_score * 0.72:
            return draft_clean
        return reviewed_clean

    @staticmethod
    def _markdown_quality_score(markdown: str) -> float:
        body = markdown.strip()
        if not body:
            return 0.0
        arabic_chars = count_arabic_characters(body)
        structure_score = 0.0
        structure_score += len(_PAGE_MARKER_RE.findall(body)) * 35.0
        structure_score += len(_ARTICLE_REF_RE.findall(body)) * 30.0
        structure_score += len(_DIGIT_RE.findall(body)) * 3.0
        structure_score += body.count("|") * 4.0
        structure_score += body.count("\n") * 1.5
        unreadable_penalty = body.count("[غير واضح]") * 40.0
        return (arabic_chars * 4.0) + float(len(body)) + structure_score - unreadable_penalty

    @staticmethod
    def _lost_page_markers(draft: str, reviewed: str) -> bool:
        draft_markers = set(_PAGE_MARKER_RE.findall(draft))
        if not draft_markers:
            return False
        reviewed_markers = set(_PAGE_MARKER_RE.findall(reviewed))
        return not draft_markers.issubset(reviewed_markers)

    @staticmethod
    def _looks_like_non_transcription(markdown: str) -> bool:
        lowered = markdown.strip().lower()
        bad_phrases = (
            "لا أستطيع",
            "لا يمكنني",
            "cannot",
            "can't",
            "i am unable",
            "as an ai",
            "validation",
            "confidence score",
        )
        return any(phrase in lowered for phrase in bad_phrases)

    @staticmethod
    def _compose_document_markdown(
        pdf_path: Path,
        result: DocumentExtractionResult,
    ) -> str:
        lines: list[str] = [
            f"# {pdf_path.stem}",
            "",
            f"> Source PDF: `{pdf_path}`",
            f"> Pages extracted: {result.processed_pages}/{result.total_pages}",
        ]
        if result.elapsed_ms:
            lines.append(f"> Elapsed: {result.elapsed_ms} ms")
        if result.model_calls:
            lines.append(f"> Model calls: {result.model_calls}")
        if result.total_tokens:
            lines.append(f"> Tokens: {result.input_tokens} in / {result.output_tokens} out / {result.total_tokens} total")
        if result.estimated_cost_usd:
            lines.append(f"> Estimated cost: ${result.estimated_cost_usd:.6f}")
        lines.append("")

        for page in result.page_results:
            lines.append(f"## الصفحة {page.page_number}")
            lines.append("")
            if page.status == "success":
                lines.append(page.markdown.strip())
            else:
                lines.append(f"[فشل الاستخراج: {page.error or 'خطأ غير معروف'}]")
            lines.append("")

        return "\n".join(lines).strip() + "\n"
