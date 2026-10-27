"""Shared limits for document ingestion, including direct OCR uploads."""

from io import BytesIO
from pathlib import Path

MAX_UPLOAD_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_DOCUMENT_PAGES = 3


class UploadSizeError(ValueError):
    pass


def validate_upload_size(size: int) -> None:
    if not 0 < size <= MAX_UPLOAD_BYTES:
        raise UploadSizeError("Choose a non-empty file up to 5 MB.")


def validate_page_count(count: int, max_pages: int = MAX_DOCUMENT_PAGES) -> None:
    limit = min(max_pages, MAX_DOCUMENT_PAGES)
    if count > limit:
        raise ValueError(
            f"This document has {count} pages or sections, which exceeds the maximum limit "
            f"of {limit} pages. Please upload a document with at most {limit} pages."
        )


def validate_pdf_pages(source: bytes | Path, max_pages: int = MAX_DOCUMENT_PAGES) -> None:
    from pypdf import PdfReader

    try:
        with BytesIO(source) if isinstance(source, bytes) else Path(source).open("rb") as stream:
            count = len(PdfReader(stream).pages)
    except Exception as exc:
        raise ValueError("This PDF could not be read. Upload a valid, unencrypted PDF.") from exc
    validate_page_count(count, max_pages)
