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


@dataclass
class PageText:
    """Text content of a single PDF page with metadata."""

    page_number: int
    text: str
    doc_name: str
    total_pages: int

    def __str__(self) -> str:
        return f"[{self.doc_name} p.{self.page_number}/{self.total_pages}] {self.text[:120]}..."


@dataclass
class PDFDocument:
    """A loaded PDF document broken into per-page text."""

    name: str
    pages: list[PageText] = field(default_factory=list)
    file_path: Optional[str] = None

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


def _fitz_loader(file_path: str | os.PathLike) -> list[PageText]:
    """
    Load a PDF using PyMuPDF (fitz) with high-quality text extraction.

    Uses ``get_text(sort=True)`` for proper reading order, extracts
    block-level text to preserve paragraph boundaries, and optionally
    extracts tables for structured data.
    """
    doc = fitz.open(str(file_path))
    pages: list[PageText] = []
    total = doc.page_count
    name = os.path.basename(str(file_path))

    for i, page in enumerate(doc):  # type: ignore[union-attr,var-annotated,arg-type]
        # --- Perfect text extraction ---
        # sort=True ensures proper reading order (top-to-bottom, left-to-right)
        text = page.get_text("text", sort=True)

        # If the page has minimal text, try the "blocks" mode which can
        # capture text in table cells or other non-standard layouts
        if len(text.strip()) < 50:
            blocks_text = page.get_text("blocks", sort=True)
            if blocks_text:
                # blocks mode returns tuples; extract the text portion
                block_texts = [b[4] for b in blocks_text if b[4]]
                if block_texts:
                    text = "\n".join(block_texts)

        # --- Optional: table extraction ---
        # PyMuPDF can detect and extract tables. We include table text
        # after the main text for completeness.
        try:
            tables = page.find_tables()
            if tables:
                table_texts = []
                for table in tables:
                    extracted = table.extract()
                    for row in extracted:
                        row_text = " | ".join(str(cell) if cell else "" for cell in row)
                        if row_text.strip():
                            table_texts.append(row_text)
                if table_texts:
                    text += "\n\n[Table data]\n" + "\n".join(table_texts)
        except Exception:
            # Table extraction is best-effort
            pass

        pages.append(
            PageText(
                page_number=i + 1,
                text=text,
                doc_name=name,
                total_pages=total,
            )
        )

    doc.close()
    return pages


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


def load_pdf(file_path: str | os.PathLike) -> PDFDocument:
    """
    Load a PDF file into a PDFDocument with per-page text and metadata.

    Uses PyMuPDF (fitz) when available for superior text quality;
    falls back to pypdf / PyPDF2 otherwise.
    """
    file_path = os.fspath(file_path)
    name = os.path.basename(file_path)

    if fitz is not None:
        pages = _fitz_loader(file_path)
    elif PdfReader is not None:
        pages = _pypdf_loader(file_path)
    else:
        raise ImportError("No PDF backend available. Install 'pymupdf' or 'pypdf'.")

    return PDFDocument(name=name, pages=pages, file_path=file_path)


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
