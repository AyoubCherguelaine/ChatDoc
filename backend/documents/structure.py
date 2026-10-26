"""
Document structure extraction — outlines, headings, and tables.

Extends the document pipeline with structural awareness so agents can
navigate by section headings, extract data tables as structured Markdown,
and jump to specific sections rather than only raw pages.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .pdf_loader import PDFDocument

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24
except ImportError:  # pragma: no cover - fallback path
    try:
        import fitz  # type: ignore[no-redef]  # PyMuPDF (older versions)
    except (ImportError, ModuleNotFoundError):
        fitz = None  # type: ignore[assignment]


@dataclass
class Heading:
    """A detected document heading / section title."""

    text: str
    page_number: int
    level: int = 1
    font_size: Optional[float] = None
    bold: bool = False

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "page": self.page_number,
            "level": self.level,
            "fontSize": self.font_size,
            "bold": self.bold,
        }


@dataclass
class TableExtract:
    """A table extracted from a page, represented as rows of cells."""

    rows: list[list[str]]
    page_number: int
    bbox: Optional[tuple[float, float, float, float]] = None

    def to_markdown(self) -> str:
        if not self.rows:
            return ""
        header = self.rows[0]
        sep = "| " + " | ".join("---" for _ in header) + " |"
        lines = [
            "| " + " | ".join(str(c) for c in header) + " |",
            sep,
        ]
        for row in self.rows[1:]:
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "page": self.page_number,
            "rows": len(self.rows),
            "columns": len(self.rows[0]) if self.rows else 0,
            "data": self.rows,
        }


def extract_outline(file_path: str | os.PathLike) -> list[Heading]:
    """
    Extract a document outline (headings) from a PDF using PyMuPDF.

    Headings are detected by:
    - PDF bookmark/outline structure (if present)
    - Font size and boldness for body-text headings
    - Numbered section patterns (e.g. ``1.``, ``1.2``)

    Returns a list of :class:`Heading` sorted by page number.
    """
    if fitz is None:
        return []

    doc = fitz.open(str(file_path))
    headings: list[Heading] = []

    # --- 1. Try PDF outline/bookmarks first ---
    try:
        toc = doc.get_toc()
        if toc:
            for entry in toc:
                level = entry[0]
                text = entry[1]
                dest = entry[2]
                page = 0
                if isinstance(dest, (list, tuple)) and dest:
                    if isinstance(dest[0], int):
                        page = dest[0] + 1  # 0-indexed
                if page == 0:
                    page = 1
                headings.append(
                    Heading(
                        text=text,
                        page_number=page,
                        level=min(level, 6),
                    )
                )
            if headings:
                doc.close()
                return headings
    except Exception:
        pass

    # --- 2. Fall back to font-based + pattern-based detection ---
    for page in doc:  # type: ignore[attr-defined]
        page_num = page.page_number + 1
        blocks = page.get_text("dict").get("blocks", [])

        # Collect candidate lines with font info
        candidates: list[Heading] = []
        max_font = 0

        for block in blocks:
            if block["type"] != 0:
                continue
            for line in block.get("lines", []):
                if not line.get("spans"):
                    continue
                span = line["spans"][0]
                text = line.get("text", "").strip()
                if not text:
                    continue
                font_size = round(span.get("size", 0), 1)
                bold = bool(span.get("flags", 0) & (1 << 16))  # bold flag in PyMuPDF
                max_font = max(max_font, font_size)

                # Numbered section heading: 1., 1.1, 2.3.4, etc.
                is_numbered = False
                if line["spans"]:
                    first = line["spans"][0]
                    first.get("text", "").strip()
                    for span in line["spans"]:
                        t = span.get("text", "")
                        stripped = t.lstrip()
                        # Check for numbering pattern at start
                        import re

                        if re.match(r"^\d+(\.\d+)*\.?\s", stripped):
                            is_numbered = True
                            break

                # Bold or large text is likely a heading
                if bold or font_size >= max_font * 0.85:
                    level = 1
                    if font_size < max_font * 0.85:
                        level = 2
                    candidates.append(
                        Heading(
                            text=text,
                            page_number=page_num,
                            level=level if not is_numbered else _number_level(text),
                            font_size=font_size,
                            bold=bold,
                        )
                    )

        # Deduplicate: keep only headings not part of a longer heading line
        seen_texts = set()
        for h in candidates:
            if h.text in seen_texts:
                continue
            seen_texts.add(h.text)
            headings.append(h)

    doc.close()
    return headings


def _number_level(text: str) -> int:
    """Determine heading level from numeric prefix like `1.2.3`."""
    import re

    m = re.match(r"^(\d+)(\.(\d+))?", text)
    if not m:
        return 1
    # Count dots / segments
    prefix = m.group(0)
    return min(prefix.count(".") + 1, 6)


def get_outline_for_document(document: PDFDocument | str | os.PathLike) -> list[Heading]:
    """Get headings for an already-loaded document or a file path."""
    if isinstance(document, str) or not isinstance(document, PDFDocument):
        return extract_outline(document)

    # Search the doc_name — but we need the file path
    file_path = getattr(document, "file_path", None)
    if file_path and os.path.exists(file_path):
        return extract_outline(file_path)
    return []


def extract_tables(
    file_path: str | os.PathLike,
    pages: Optional[list[int]] = None,
) -> list[TableExtract]:
    """
    Extract all tables from a PDF using PyMuPDF's table finder.

    Parameters
    ----------
    file_path
        Path to the PDF file.
    pages
        Optional list of 1-indexed page numbers to extract from.
        If None, extracts from all pages.
    """
    if fitz is None:
        return []

    doc = fitz.open(str(file_path))
    result: list[TableExtract] = []

    for page in doc:  # type: ignore[attr-defined]
        page_num = page.page_number + 1
        if pages is not None and page_num not in pages:
            continue

        try:
            tables = page.find_tables()
            for table in tables:
                extracted = table.extract()
                if extracted:
                    # Clean up cell content
                    rows = [
                        [str(cell).strip() if cell else "" for cell in row]
                        for row in extracted
                    ]
                    bbox = tuple(table.bbox) if table.bbox else None
                    result.append(
                        TableExtract(
                            rows=rows,
                            page_number=page_num,
                            bbox=bbox,
                        )
                    )
        except Exception:
            # Table extraction is best-effort
            continue

    doc.close()
    return result


def extract_page_outline(document: PDFDocument, page_num: int) -> list[Heading]:
    """Get headings that appear on or reference a specific page."""
    file_path = getattr(document, "file_path", None)
    if not file_path or not os.path.exists(file_path):
        return []

    headings = extract_outline(file_path)
    return [h for h in headings if h.page_number <= page_num]


def section_text(document: PDFDocument, section_title: str, context_lines: int = 5) -> str:
    """
    Get text around a section heading (heading + next few lines of content).

    Searches the document's loaded PDFDocument pages for a heading.
    """
    target = section_title.lower().strip()
    for page in document.pages:
        lines = page.text.split("\n")
        for i, line in enumerate(lines):
            if target in line.lower().strip():
                start = max(0, i)
                end = min(len(lines), i + 1 + context_lines)
                return "\n".join(lines[start:end])
    return ""


# ---------------------------------------------------------------------------
# Non-PDF outline helper (for DOCX/XLSX/CSV/TXT loaded as PDFDocument)
# ---------------------------------------------------------------------------


def extract_text_outline(document: PDFDocument) -> list[Heading]:
    """
    Extract headings from a non-PDF document by detecting
    heading-like lines (bold-style patterns, numbered sections, etc.).

    This works on the already-loaded ``PDFDocument`` pages.
    """
    import re

    headings: list[Heading] = []

    for page in document.pages:
        lines = page.text.split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Numbered section pattern: 1.  1.1  2.3.4
            if re.match(r"^\d+(\.\d+)*\.?\s+.+", stripped):
                level = stripped[: stripped.find(" ")].count(".")
                headings.append(
                    Heading(
                        text=stripped,
                        page_number=page.page_number,
                        level=min(level + 1, 6),
                    )
                )
                continue

            # ALL CAPS short line (likely a section header)
            if (
                stripped.isupper()
                and len(stripped.split()) <= 6
                and 3 <= len(stripped) <= 60
            ):
                headings.append(
                    Heading(
                        text=stripped,
                        page_number=page.page_number,
                        level=1,
                    )
                )

    return headings
