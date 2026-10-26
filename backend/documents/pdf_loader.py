"""
PDF document loader with page-level metadata using PyMuPDF.

Provides robust page-level text extraction so that the agent can read
specific pages (the "document tools to read special pages" requirement)
and the vector store can track which page each chunk originated from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Sequence

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24
except ImportError:
    try:
        import fitz  # type: ignore[no-redef]  # PyMuPDF (older versions)
    except (ImportError, ModuleNotFoundError):
        fitz = None  # type: ignore[assignment]

try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader  # type: ignore[no-redef]
    except ImportError:
        PdfReader = None  # type: ignore[misc]


from pathlib import Path


@dataclass
class PageText:
    """Text content of a single PDF page with metadata."""

    page_number: int
    text: str
    doc_name: str
    total_pages: int
    tables: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    structured_json: Optional[dict] = None
    is_ocr: bool = False

    def __str__(self) -> str:
        return f"[{self.doc_name} p.{self.page_number}/{self.total_pages}] {self.text[:120]}..."


@dataclass
class PDFDocument:
    """A loaded PDF document broken into per-page text."""

    name: str
    pages: list[PageText] = field(default_factory=list)
    file_path: Optional[str] = None
    structured_data: Optional[dict] = None
    is_ocr: bool = False

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    def get_page(self, page_number: int) -> Optional[PageText]:
        if page_number < 1 or page_number > len(self.pages):
            return None
        return self.pages[page_number - 1]

    def get_pages(self, start: int, end: int) -> list[PageText]:
        pages = []
        for p in range(max(1, start), min(end, len(self.pages)) + 1):
            page = self.get_page(p)
            if page:
                pages.append(page)
        return pages


def _fitz_loader(
    file_path: str | os.PathLike,
    force_ocr: bool = False,
) -> tuple[list[PageText], Optional[dict]]:
    """
    Load a PDF using PyMuPDF (fitz) with layout-aware blocks,
    GitHub Flavored Markdown table extraction, and automatic vision OCR
    for scanned or complex tabular/transactional documents.
    """
    doc = fitz.open(str(file_path))
    pages: list[PageText] = []
    total = doc.page_count
    name = os.path.basename(str(file_path))
    doc_structured_json: Optional[dict] = None

    for i, page in enumerate(doc):  # type: ignore[union-attr,var-annotated,arg-type]
        # 1. Blocks-aware text extraction to preserve paragraph boundaries and headings
        text = str(page.get_text("text", sort=True) or "")
        block_texts: list[str] = []
        try:
            raw_blocks = page.get_text("blocks", sort=True)
            if isinstance(raw_blocks, list):
                for b in raw_blocks:
                    if isinstance(b, (tuple, list)) and len(b) > 4:
                        b_text = str(b[4]).strip() if b[4] else ""
                        b_type = b[6] if len(b) > 6 else 0
                        if b_type == 0 and b_text:
                            block_texts.append(b_text)
                if block_texts:
                    text = "\n\n".join(block_texts)
        except Exception:
            pass

        # 2. Extract structured Markdown GFM tables
        table_md_list: list[str] = []
        try:
            tab_finder = page.find_tables()
            if tab_finder and getattr(tab_finder, "tables", None):
                for table in tab_finder.tables:
                    extracted = table.extract()
                    if extracted and len(extracted) >= 1:
                        raw_headers = [str(c).strip().replace("\n", " ") if c is not None else "" for c in extracted[0]]
                        if not any(raw_headers):
                            continue
                        cols = len(raw_headers)
                        headers = [h or f"Column_{idx+1}" for idx, h in enumerate(raw_headers)]
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
                            table_lines.append("| " + " | ".join(cells) + " |")
                        table_md_list.append("\n".join(table_lines))
                if table_md_list:
                    text += "\n\n### Extracted Tables\n\n" + "\n\n".join(table_md_list)
        except Exception:
            pass

        # 3. Vision OCR fallback for scanned pages or when OCR is explicitly forced
        is_ocr = False
        page_structured_json = None
        has_sparse_text = len(text.strip()) < 80
        if has_sparse_text or force_ocr:
            try:
                from backend.agent.tools.ocr import OcrService
                ocr_svc = OcrService()
                ocr_output = ocr_svc.ocr_read_page(Path(file_path), i + 1)
                if ocr_output and not ocr_output.startswith("ERROR:"):
                    text = ocr_output
                    is_ocr = True
            except Exception:
                pass

        # 4. Check for structured data (e.g. invoice, receipt, contract)
        try:
            from backend.v1.routes import _extract_json_from_text, extract_structured_data
            parsed = _extract_json_from_text(text)
            if parsed and isinstance(parsed, dict) and len(parsed) > 1:
                page_structured_json = parsed
                if doc_structured_json is None:
                    doc_structured_json = parsed
            elif any(kw in text.lower() for kw in ["invoice", "فاتورة", "receipt", "إيصال", "subtotal", "tax invoice"]):
                prose_json = extract_structured_data(text, service="invoice")
                if prose_json and len(prose_json) > 1 and "summary" not in prose_json:
                    page_structured_json = prose_json
                    if doc_structured_json is None:
                        doc_structured_json = prose_json
        except Exception:
            pass

        pages.append(
            PageText(
                page_number=i + 1,
                text=text,
                doc_name=name,
                total_pages=total,
                tables=table_md_list,
                blocks=block_texts,
                structured_json=page_structured_json,
                is_ocr=is_ocr,
            )
        )

    doc.close()
    return pages, doc_structured_json


def _pypdf_loader(file_path: str | os.PathLike) -> list[PageText]:
    """Fallback loader using pypdf/PyPDF2."""
    reader = PdfReader(str(file_path))
    pages: list[PageText] = []
    total = len(reader.pages)
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append(
            PageText(
                page_number=i + 1,
                text=text,
                doc_name=os.path.basename(str(file_path)),
                total_pages=total,
            )
        )
    return pages


def load_pdf(
    file_path: str | os.PathLike,
    force_ocr: bool = False,
) -> PDFDocument:
    """
    Load a PDF file into a PDFDocument with per-page text and metadata.

    Uses PyMuPDF (fitz) when available with layout blocks, Markdown tables,
    and automatic vision OCR for scanned or non-standard documents.
    """
    file_path = os.fspath(file_path)
    name = os.path.basename(file_path)
    structured_data = None

    if fitz is not None:
        pages, structured_data = _fitz_loader(file_path, force_ocr=force_ocr)
    elif PdfReader is not None:
        pages = _pypdf_loader(file_path)
    else:
        raise ImportError("No PDF backend available. Install 'pymupdf' or 'pypdf'.")

    is_any_ocr = any(p.is_ocr for p in pages)
    return PDFDocument(
        name=name,
        pages=pages,
        file_path=file_path,
        structured_data=structured_data,
        is_ocr=is_any_ocr,
    )


def load_pdfs(
    file_paths: Sequence[str | os.PathLike],
) -> list[PDFDocument]:
    """Load multiple PDFs and return a list of PDFDocument objects."""
    return [load_pdf(fp) for fp in file_paths]


def get_page_count(file_path: str | os.PathLike) -> int:
    """Return the number of pages in a PDF without loading full text."""
    if fitz is not None:
        doc = fitz.open(str(file_path))
        count = doc.page_count
        doc.close()
        return count
    if PdfReader is not None:
        return len(PdfReader(str(file_path)).pages)
    raise ImportError("No PDF backend available. Install 'pymupdf' or 'pypdf'.")


def extract_page_text(file_path: str | os.PathLike, page_number: int) -> str:
    """
    Extract text from a specific 1-indexed page of a PDF.

    Used by the agent's read_page tool for reading 'special pages'.
    """
    doc = load_pdf(file_path)
    page = doc.get_page(page_number)
    if page is None:
        raise ValueError(f"Page {page_number} is out of range (document has {doc.total_pages} pages).")
    return page.text


def extract_pages_text(file_path: str | os.PathLike, start_page: int, end_page: int) -> str:
    """Extract concatenated text from a range of pages (1-indexed, inclusive)."""
    doc = load_pdf(file_path)
    pages = doc.get_pages(start_page, end_page)
    if not pages:
        raise ValueError(f"Pages {start_page}-{end_page} are out of range (document has {doc.total_pages} pages).")
    return "\n\n".join(p.text for p in pages)
