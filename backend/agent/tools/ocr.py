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
            if pdfium is not None:
                return pdfium
        except (ImportError, ModuleNotFoundError):
            pass
        raise OcrError("Missing dependency 'pypdfium2'. Install with: pip install pypdfium2")

    def page_count(self, pdf_path: Path) -> int:
        pdf_path = Path(pdf_path)
        # Try pypdfium2 if present
        try:
            import pypdfium2 as pdfium  # type: ignore
            if pdfium is not None:
                document = pdfium.PdfDocument(str(pdf_path))
                try:
                    return len(document)
                finally:
                    document.close()
        except OcrError:
            raise
        except Exception:
            pass

        # Try fitz (PyMuPDF)
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            try:
                return doc.page_count
            finally:
                doc.close()
        except Exception:
            pass

        # Fallback to trigger descriptive error
        pdfium = self._pdfium_module()
        document = pdfium.PdfDocument(str(pdf_path))
        return len(document)

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
        pdf_path = Path(pdf_path)
        # Try pypdfium2 first
        try:
            import pypdfium2 as pdfium  # type: ignore
            if pdfium is not None:
                document = pdfium.PdfDocument(str(pdf_path))
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
        except Exception:
            pass

        # Try fitz (PyMuPDF)
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            try:
                if page_number < 1 or page_number > doc.page_count:
                    return None
                page = doc[page_number - 1]
                pix = page.get_pixmap(dpi=dpi)
                return pix.tobytes("png")
            finally:
                doc.close()
        except Exception as exc:
            raise OcrError(f"Failed to open/render PDF {pdf_path}: {exc}") from exc

        return None

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


OCR_PAGE_PROMPT = """\
You are an advanced document OCR and layout analysis engine.
Transcribe the content visible in this page image with 100% precision.

Formatting guidelines:
1. Preserve structural layout using markdown: headings (##, ###), bullet lists, and paragraphs.
2. Render all tabular data (pricing tables, line items, account balances, tax columns) as GitHub Flavored Markdown (GFM) tables:
| Description | Qty | Unit Price | Total |
|---|---|---|---|
| Item Name | 1 | 100.00 | 100.00 |
3. Capture both Arabic and English text in correct reading order and typography.
4. If this page contains a transaction, invoice, receipt, contract, or form, append a clean structured JSON block at the bottom:
```json
{
  "document_type": "invoice|receipt|contract|form|statement|other",
  ...
}
```
Do not output extraneous conversational filler. Output the transcribed document layout directly.
"""


INVOICE_OCR_PROMPT = """You are an invoice data extraction engine. Analyse the invoice image and extract structured data. Return ONLY valid JSON. Include: vendor (name, address, email, phone), client (name, address, email), invoice_number, invoice_date (ISO YYYY-MM-DD), due_date (ISO YYYY-MM-DD), currency, line_items (list of {description, quantity, unit_price, amount}), subtotal, tax_total, tax_rate, total, payment_terms, po_number, notes. Do not add any explanation outside the JSON. If a field is not visible, use null."""


CONTRACT_OCR_PROMPT = """You are a contract analysis engine. Analyse the contract image and extract structured data. Return ONLY valid JSON. Include: parties (list of {name, address, email, role}), effective_date (ISO), expiration_date (ISO), renewal_terms, termination_notice, governing_law, jurisdiction, dispute_resolution, key_clauses (list of {name, text}), payment_terms, obligations, risk_flags (list of {flag, severity, clause, recommendation}). If a field is not visible, use null. Do not add any explanation outside the JSON."""



def detect_block_language(text: str) -> tuple[str, str]:
    """Detect whether block content is Arabic ('ar', 'rtl'), English ('en', 'ltr'), or Mixed ('mixed', 'rtl')."""
    if not text:
        return "en", "ltr"
    import re
    arabic_chars = len(re.findall(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))
    total = arabic_chars + latin_chars
    if total == 0:
        return "en", "ltr"
    ratio = arabic_chars / total
    if ratio > 0.55:
        return "ar", "rtl"
    elif ratio < 0.15:
        return "en", "ltr"
    else:
        return "mixed", "rtl" if ratio >= 0.5 else "ltr"


def extract_native_page_blocks(pdf_path: Path, page_number: int, llm: Optional[Any] = None) -> list[dict]:
    """Extract structural layout blocks (titles, text, tables, images) from a native PDF page using PyMuPDF."""
    try:
        import fitz
    except ImportError:
        return []

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return []

    doc = fitz.open(str(pdf_path))
    try:
        if page_number < 1 or page_number > doc.page_count:
            return []
        page = doc[page_number - 1]

        # 1. Detect tables
        table_blocks: list[dict] = []
        table_rects: list[fitz.Rect] = []
        try:
            tabs = page.find_tables()
            if tabs and getattr(tabs, "tables", None):
                for t in tabs.tables:
                    extracted = t.extract()
                    if extracted and len(extracted) >= 1:
                        raw_headers = [str(c).strip().replace("\n", " ") if c is not None else "" for c in extracted[0]]
                        if not any(raw_headers):
                            continue
                        cols = max(len(raw_headers), 1)
                        headers = [h or f"Column_{idx+1}" for idx, h in enumerate(raw_headers)]
                        rows: list[list[str]] = []
                        table_lines = [
                            "| " + " | ".join(headers) + " |",
                            "| " + " | ".join(["---"] * cols) + " |",
                        ]
                        for row in extracted[1:]:
                            cells = [str(c).strip().replace("\n", " ") if c is not None else "" for c in row]
                            if len(cells) < cols:
                                cells.extend([""] * (cols - len(cells)))
                            elif len(cells) > cols:
                                cells = cells[:cols]
                            rows.append(cells)
                            table_lines.append("| " + " | ".join(cells) + " |")

                        content_md = "\n".join(table_lines)
                        bbox = [round(float(v), 2) for v in list(t.bbox)]
                        t_rect = fitz.Rect(t.bbox)
                        table_rects.append(t_rect)
                        t_lang, t_dir = detect_block_language(content_md)
                        table_blocks.append({
                            "type": "table",
                            "content": content_md,
                            "metadata": {
                                "page_number": page_number,
                                "bbox": bbox,
                                "language": t_lang,
                                "direction": t_dir,
                                "confidence": 0.99,
                            },
                            "table": {
                                "content_md": content_md,
                                "headers": headers,
                                "rows": rows,
                                "row_count": len(rows),
                                "col_count": cols,
                            },
                        })
        except Exception as exc:
            logger.debug("Table detection failed: %s", exc)

        # 2. Extract text & title blocks
        text_blocks: list[dict] = []
        try:
            d = page.get_text("dict")
            blocks_data = d.get("blocks", [])

            # Compute median font size across the page
            font_sizes: list[float] = []
            for b in blocks_data:
                if b.get("type") == 0:
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get("text", "").strip():
                                font_sizes.append(float(span.get("size", 10.0)))
            median_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 10.0

            for b in blocks_data:
                if b.get("type") != 0:
                    continue
                b_bbox = [round(float(v), 2) for v in list(b.get("bbox", [0, 0, 0, 0]))]
                r = fitz.Rect(b.get("bbox"))

                # Skip if block is already captured inside an extracted table
                if any(r in tr or (r & tr).get_area() > 0.45 * r.get_area() for tr in table_rects):
                    continue

                lines_text: list[str] = []
                max_span_size = 0.0
                is_bold = False
                for line in b.get("lines", []):
                    line_str = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                    for span in line.get("spans", []):
                        s_size = float(span.get("size", 10.0))
                        if s_size > max_span_size:
                            max_span_size = s_size
                        flags = span.get("flags", 0)
                        if flags & 2 or flags & 16:
                            is_bold = True
                    if line_str:
                        lines_text.append(line_str)

                full_text = "\n".join(lines_text).strip()
                if not full_text:
                    continue

                # Classify title vs body text
                is_title = (
                    (max_span_size >= median_size * 1.25 and len(full_text.splitlines()) <= 3 and len(full_text) < 140)
                    or (is_bold and len(full_text) < 80 and len(full_text.splitlines()) == 1)
                    or full_text.startswith(("# ", "## ", "### "))
                )

                txt_lang, txt_dir = detect_block_language(full_text)
                block_item: dict[str, Any] = {
                    "type": "title" if is_title else "text",
                    "content": full_text,
                    "metadata": {
                        "page_number": page_number,
                        "language": txt_lang,
                        "direction": txt_dir,
                        "bbox": b_bbox,
                        "confidence": 0.99,
                        "font_size": round(max_span_size, 1),
                        "is_bold": is_bold,
                    },
                }
                if is_title:
                    clean_title = full_text.lstrip("#").strip()
                    block_item["title"] = clean_title

                text_blocks.append(block_item)
        except Exception as exc:
            logger.debug("Text block extraction failed: %s", exc)

        # 3. Detect images / figures
        image_blocks: list[dict] = []
        try:
            img_list = page.get_images()
            seen_rects: set[tuple] = set()
            for img in img_list:
                xref = img[0]
                rects = page.get_image_rects(xref)
                for r in rects:
                    bbox_tuple = (round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1))
                    if bbox_tuple in seen_rects:
                        continue
                    seen_rects.add(bbox_tuple)
                    bbox = [round(float(v), 2) for v in list(r)]

                    # Concise description of visual element ("lil describe")
                    w, h = int(r.width), int(r.height)
                    if w < 140 and h < 140 and r.y0 < 160:
                        desc = "Header logo / crest emblem"
                    elif w > 200 and h > 120:
                        desc = f"Visual figure, chart, or diagram ({w}x{h} pt)"
                    elif h < 60 and w > 100:
                        desc = "Banner header / graphical rule"
                    else:
                        desc = f"Document visual graphic / embedded image ({w}x{h} pt)"

                    image_blocks.append({
                        "type": "image",
                        "content": f"[Image: {desc}]",
                        "metadata": {
                            "page_number": page_number,
                            "language": "en",
                            "direction": "ltr",
                            "bbox": bbox,
                            "confidence": 0.95,
                        },
                        "image": {
                            "description": desc,
                            "ocr_text": "",
                            "width": w,
                            "height": h,
                            "bbox": bbox,
                        },
                    })
        except Exception as exc:
            logger.debug("Image block detection failed: %s", exc)

        # 4. Merge, sort top-to-bottom reading order, and index
        all_blocks = text_blocks + table_blocks + image_blocks
        all_blocks.sort(
            key=lambda blk: (
                blk.get("metadata", {}).get("bbox", [0, 0, 0, 0])[1],
                blk.get("metadata", {}).get("bbox", [0, 0, 0, 0])[0],
            )
        )
        for idx, blk in enumerate(all_blocks, start=1):
            blk.setdefault("metadata", {})["reading_order"] = idx

        return all_blocks
    finally:
        doc.close()


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
            from backend.config import settings

            self.llm = get_llm(model_name=settings.DEFAULT_MODEL)
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

    def ocr_read_page_blocks(
        self,
        pdf_path: Path,
        page_number: int,
        language: str = "auto",
        force_ocr: bool = False,
    ) -> dict:
        """Return semantic regions plus complete OCR transcription for one page."""
        return self.ocr_extract_blocks(
            pdf_path, page_number=page_number, language=language, force_ocr=force_ocr,
        )["pages"][0]

    def ocr_extract_blocks(
        self,
        pdf_path: Path,
        page_number: Optional[int] = None,
        language: str = "auto",
        force_ocr: bool = False,
    ) -> dict:
        """Extract semantic structure and verbatim OCR using the shared vision engine.

        ``force_ocr`` remains accepted for existing callers; semantic extraction
        always reads the rendered page, including PDFs with a native text layer.
        Coordinates use the shared normalized 0..1000 canvas.
        """
        from backend.agent.tools.advanced_ocr import AdvancedOcrService

        engine = AdvancedOcrService(
            llm=self.llm, renderer=self.renderer, dpi=self.dpi, max_pages=self.max_pages,
        )
        if page_number is not None:
            data = engine.extract(pdf_path, start_page=page_number, end_page=page_number, language=language)
            data["page_number"] = page_number
        else:
            total = self.renderer.page_count(Path(pdf_path))
            data = engine.extract(pdf_path, end_page=min(total, self.max_pages or 50), language=language)
        self.llm = engine.llm
        for page in data["pages"]:
            for block in page["blocks"]:
                detected, direction = detect_block_language(block["ocr_text"])
                meta = block.get("metadata")
                meta = dict(meta) if isinstance(meta, dict) else {}
                meta.update(
                    page_number=block["page_number"], reading_order=block["reading_order"],
                    bbox=block["bbox"], coordinate_system=data["coordinate_system"],
                    language=detected, direction=direction,
                )
                block["metadata"] = meta
                # Retain the convenience fields consumed by existing clients.
                if block["type"] == "title":
                    block.setdefault("title", block["ocr_text"])
                if block["type"] == "table":
                    table = block.get("table")
                    table = dict(table) if isinstance(table, dict) else {}
                    table.setdefault("content_md", block["ocr_text"])
                    block["table"] = table
                if block["type"] == "image":
                    image = block.get("image")
                    image = dict(image) if isinstance(image, dict) else {}
                    content = block["content"]
                    description = content.get("description", "") if isinstance(content, dict) else content
                    image.setdefault("description", description)
                    image["ocr_text"] = block["ocr_text"]
                    block["image"] = image
            page["language_detected"], page["direction"] = detect_block_language(page["ocr_text"])
        data["language_detected"], data["direction"] = detect_block_language(data["ocr_text"])
        return data


def extract_invoice_json(ocr_service: OcrService, pdf_path: Path) -> str:
    """Convenience function: OCR a PDF and extract invoice data as JSON."""
    return ocr_service.ocr_extract_invoice(pdf_path)


def extract_contract_json(ocr_service: OcrService, pdf_path: Path) -> str:
    """Convenience function: OCR a PDF and extract contract data as JSON."""
    return ocr_service.ocr_extract_contract(pdf_path)


def extract_blocks_json(
    ocr_service: OcrService,
    pdf_path: Path,
    page_number: Optional[int] = None,
    force_ocr: bool = False,
) -> dict:
    """Convenience function: Extract layout blocks from a document as a JSON dictionary."""
    return ocr_service.ocr_extract_blocks(pdf_path, page_number=page_number, force_ocr=force_ocr)
