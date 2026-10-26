from __future__ import annotations

import io
from pathlib import Path

from arabic_pdf_md_agent.base.errors import PdfOcrDependencyError, PdfOcrProcessingError


class PdfChunker:
    """Create page-range PDF chunks for document-first model calls."""

    @staticmethod
    def _pypdf_modules():
        try:
            from pypdf import PdfReader, PdfWriter  # type: ignore
        except ImportError as error:  # pragma: no cover - dependency/environment issue
            raise PdfOcrDependencyError(
                "Missing dependency 'pypdf'. Install requirements before running chunked OCR."
            ) from error
        return PdfReader, PdfWriter

    def make_chunk_bytes(self, pdf_path: Path, start_page: int, end_page: int) -> bytes:
        PdfReader, PdfWriter = self._pypdf_modules()
        try:
            reader = PdfReader(str(pdf_path))
        except Exception as error:  # pragma: no cover - library/environment specific
            raise PdfOcrProcessingError(f"Failed to open PDF {pdf_path}: {error}") from error
        writer = PdfWriter()

        start_idx = max(1, start_page) - 1
        end_idx = max(start_idx, end_page - 1)
        for idx in range(start_idx, min(end_idx + 1, len(reader.pages))):
            writer.add_page(reader.pages[idx])

        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
