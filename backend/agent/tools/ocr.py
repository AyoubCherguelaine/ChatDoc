"""
OCR tools for the agent framework.

Adapted from the standalone ``pdf_ocr_service`` project to work within this
project's agent architecture.  Supports vision-based extraction from scanned
PDFs using OpenAI-compatible vision models (e.g. ``gpt-4o`` / ``gpt-4o-mini``).

Key capabilities:
* ``ocr_read_page``       — render a PDF page to an image and run OCR
* ``ocr_extract_invoice`` — extract structured invoice data as JSON
* ``ocr_extract_contract``— extract structured contract data as JSON
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OcrError(Exception):
    """Raised when OCR processing fails."""


class PdfRenderer:
    """Render PDF pages into PNG bytes for vision models.

    Adapted from ``pdf_ocr_service``'s ``PdfRenderer`` — uses ``pypdfium2`` for
    high-quality rendering.
    """

    @staticmethod
    def _pdfium_module():
        try:
            import pypdfium2 as pdfium  # type: ignore
        except ImportError as exc:
            raise OcrError(
                "Missing dependency 'pypdfium2'. Install with: pip install pypdfium2"
            ) from exc
        return pdfium

    def page_count(self, pdf_path: Path) -> int:
        pdfium = self._pdfium_module()
        try:
            document = pdfium.PdfDocument(str(pdf_path))
        except Exception as exc:
            raise OcrError(f"Failed to open PDF {pdf_path}: {exc}") from exc
        try:
            return len(document)
        finally:
            document.close()

    @staticmethod
    def _render_page_to_png(page, scale: float) -> bytes:
        bitmap = page.render(scale=scale)
        try:
            image = bitmap.to_pil()
            try:
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue()
            finally:
                image.close()
        finally:
            bitmap.close()
            page.close()

    def render_page(
        self,
        pdf_path: Path,
        page_number: int,
        dpi: int = 260,
    ) -> Optional[bytes]:
        """Render a single 1-indexed page to PNG bytes."""
        pdfium = self._pdfium_module()
        try:
            document = pdfium.PdfDocument(str(pdf_path))
        except Exception as exc:
            raise OcrError(f"Failed to open PDF {pdf_path}: {exc}") from exc

        page_total = len(document)
        if page_number < 1 or page_number > page_total:
            document.close()
            return None

        scale = max(dpi, 72) / 72.0
        try:
            page = document[page_number - 1]
            return self._render_page_to_png(page=page, scale=scale)
        finally:
            document.close()

    def render_pages(
        self,
        pdf_path: Path,
        dpi: int = 260,
        max_pages: Optional[int] = None,
    ) -> list[tuple[int, bytes]]:
        """Render all (or up to ``max_pages``) pages to PNG bytes."""
        pdfium = self._pdfium_module()
        try:
            document = pdfium.PdfDocument(str(pdf_path))
        except Exception as exc:
            raise OcrError(f"Failed to open PDF {pdf_path}: {exc}") from exc

        page_total = len(document)
        limit = min(page_total, max_pages) if max_pages else page_total
        scale = max(dpi, 72) / 72.0
        results: list[tuple[int, bytes]] = []
        try:
            for page_idx in range(limit):
                page = document[page_idx]
                results.append((page_idx + 1, self._render_page_to_png(page=page, scale=scale)))
        finally:
            document.close()
        return results


OCR_PAGE_PROMPT = """You are a precise OCR engine. Transcribe the text visible in this image exactly as it appears. Do not summarize, translate, or add commentary. If text is unclear, write [unclear]. Return plain text."""


INVOICE_OCR_PROMPT = """You are an invoice data extraction engine. Analyse the invoice image and extract structured data. Return ONLY valid JSON. Include: vendor (name, address, email, phone), client (name, address, email), invoice_number, invoice_date (ISO YYYY-MM-DD), due_date (ISO YYYY-MM-DD), currency, line_items (list of {description, quantity, unit_price, amount}), subtotal, tax_total, tax_rate, total, payment_terms, po_number, notes. Do not add any explanation outside the JSON. If a field is not visible, use null."""


CONTRACT_OCR_PROMPT = """You are a contract analysis engine. Analyse the contract image and extract structured data. Return ONLY valid JSON. Include: parties (list of {name, address, email, role}), effective_date (ISO), expiration_date (ISO), renewal_terms, termination_notice, governing_law, jurisdiction, dispute_resolution, key_clauses (list of {name, text}), payment_terms, obligations, risk_flags (list of {flag, severity, clause, recommendation}). If a field is not visible, use null. Do not add any explanation outside the JSON."""


class OcrService:
    """Vision-based OCR service for extracting text and structured data from PDFs.

    Uses OpenAI-compatible vision models (ChatOpenAI with vision support).
    """

    def __init__(
        self,
        llm: Any = None,
        renderer: Optional[PdfRenderer] = None,
        dpi: int = 260,
        max_pages: Optional[int] = None,
    ):
        self.llm = llm
        self.renderer = renderer or PdfRenderer()
        self.dpi = dpi
        self.max_pages = max_pages

    def _ensure_llm(self) -> Any:
        if self.llm is not None:
            return self.llm
        try:
            from backend.chat.chatWithVSDB import get_llm

            self.llm = get_llm(model_name="gpt-4o")
            return self.llm
        except Exception as exc:
            raise OcrError(f"Could not initialise an LLM: {exc}") from exc

    @staticmethod
    def _image_to_base64(image_bytes: bytes) -> str:
        import base64

        return base64.b64encode(image_bytes).decode("ascii")

    def ocr_read_page(self, pdf_path: Path, page_number: int) -> str:
        """Render a PDF page and OCR it to text."""
        llm = self._ensure_llm()
        image_bytes = self.renderer.render_page(pdf_path, page_number, dpi=self.dpi)
        if image_bytes is None:
            return f"ERROR: Page {page_number} not found in document."

        b64 = self._image_to_base64(image_bytes)
        try:
            from langchain_core.messages import HumanMessage

            msg = HumanMessage(
                content=[
                    {"type": "text", "text": OCR_PAGE_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]
            )
            response = llm.invoke([msg])
            text = response.content if hasattr(response, "content") else str(response)
            return text.strip() if isinstance(text, str) else str(text)
        except Exception as exc:
            return f"ERROR: OCR failed on page {page_number}: {exc}"

    def ocr_read_pages(self, pdf_path: Path, start: int, end: int) -> str:
        """OCR a range of pages and concatenate the text."""
        results = []
        total = self.renderer.page_count(pdf_path)
        for page_num in range(start, min(end, total) + 1):
            text = self.ocr_read_page(pdf_path, page_num)
            if text and not text.startswith("ERROR"):
                results.append(f"--- Page {page_num} ---\n{text}")
            if text.startswith("ERROR"):
                results.append(f"--- Page {page_num} ---\n{text}")
        return "\n\n".join(results)

    def ocr_extract_invoice(self, pdf_path: Path, page_number: Optional[int] = None) -> str:
        """OCR invoice pages and extract structured data as JSON."""
        llm = self._ensure_llm()

        if page_number is not None:
            pages_to_process = [(page_number, self.renderer.render_page(pdf_path, page_number, dpi=self.dpi))]
        else:
            pages_to_process = []
            total = min(self.renderer.page_count(pdf_path), self.max_pages or 1)
            for i in range(1, total + 1):
                img = self.renderer.render_page(pdf_path, i, dpi=self.dpi)
                if img is not None:
                    pages_to_process.append((i, img))

        if not pages_to_process:
            return "ERROR: Could not render any pages."

        if len(pages_to_process) == 1:
            return self._ocr_image_with_prompt(pages_to_process[0][1], INVOICE_OCR_PROMPT)
        return self._ocr_multi_page_invoice(pages_to_process, llm)

    def _ocr_image_with_prompt(self, image_bytes: bytes, prompt: str) -> str:
        llm = self._ensure_llm()
        b64 = self._image_to_base64(image_bytes)
        try:
            from langchain_core.messages import HumanMessage

            msg = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]
            )
            response = llm.invoke([msg])
            text = response.content if hasattr(response, "content") else str(response)
            return text.strip() if isinstance(text, str) else str(text)
        except Exception as exc:
            return f"ERROR: OCR extraction failed: {exc}"

    def _ocr_multi_page_invoice(self, pages: list[tuple[int, bytes]], llm: Any) -> str:
        """Process multiple invoice pages by sending the first page, then refining with subsequent pages."""
        first_result = self._ocr_image_with_prompt(pages[0][1], INVOICE_OCR_PROMPT)
        for page_num, image_bytes in pages[1:]:
            try:
                from langchain_core.messages import HumanMessage
                b64 = self._image_to_base64(image_bytes)
                refinement_prompt = (
                    f"Here is the current extracted invoice JSON:\n{first_result}\n\n"
                    f"Now process page {page_num} of the same invoice. Update the JSON "
                    f"with any additional line items, adjustments to totals, or new data. "
                    f"Return the complete updated JSON only."
                )
                msg = HumanMessage(
                    content=[
                        {"type": "text", "text": refinement_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ]
                )
                response = llm.invoke([msg])
                text = response.content if hasattr(response, "content") else str(response)
                first_result = text.strip() if isinstance(text, str) else str(text)
            except Exception as exc:
                logger.warning("Failed to process page %d: %s", page_num, exc)
        return first_result

    def ocr_extract_contract(self, pdf_path: Path, page_number: Optional[int] = None) -> str:
        """OCR contract pages and extract structured data as JSON."""
        if page_number is not None:
            image_bytes = self.renderer.render_page(pdf_path, page_number, dpi=self.dpi)
            if image_bytes is None:
                return f"ERROR: Page {page_number} not found."
            return self._ocr_image_with_prompt(image_bytes, CONTRACT_OCR_PROMPT)

        pages_to_process: list[tuple[int, bytes]] = []
        total = min(self.renderer.page_count(pdf_path), self.max_pages or 1)
        for i in range(1, total + 1):
            img = self.renderer.render_page(pdf_path, i, dpi=self.dpi)
            if img is not None:
                pages_to_process.append((i, img))

        if not pages_to_process:
            return "ERROR: Could not render any pages."

        first_result = self._ocr_image_with_prompt(pages_to_process[0][1], CONTRACT_OCR_PROMPT)
        llm = self._ensure_llm()
        for page_num, image_bytes in pages_to_process[1:]:
            try:
                from langchain_core.messages import HumanMessage
                b64 = self._image_to_base64(image_bytes)
                refinement_prompt = (
                    f"Current extracted contract JSON:\n{first_result}\n\n"
                    f"Process page {page_num} of the same contract. Update the JSON "
                    f"with additional clauses, obligations, or risk flags found. "
                    f"Return the complete updated JSON only."
                )
                msg = HumanMessage(
                    content=[
                        {"type": "text", "text": refinement_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ]
                )
                response = llm.invoke([msg])
                text = response.content if hasattr(response, "content") else str(response)
                first_result = text.strip() if isinstance(text, str) else str(text)
            except Exception as exc:
                logger.warning("Failed to process page %d: %s", page_num, exc)
        return first_result


def extract_invoice_json(ocr_service: OcrService, pdf_path: Path) -> str:
    """Convenience function: OCR a PDF and extract invoice data as JSON."""
    return ocr_service.ocr_extract_invoice(pdf_path)


def extract_contract_json(ocr_service: OcrService, pdf_path: Path) -> str:
    """Convenience function: OCR a PDF and extract contract data as JSON."""
    return ocr_service.ocr_extract_contract(pdf_path)
