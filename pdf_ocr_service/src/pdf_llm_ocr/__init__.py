"""Public API for Gemini-powered PDF-to-Markdown OCR."""

from arabic_pdf_md_agent.agent import ArabicPdfMdCoordinator, run_extraction
from arabic_pdf_md_agent.base.errors import (
    PdfOcrDependencyError,
    PdfOcrError,
    PdfOcrExternalServiceError,
    PdfOcrInputError,
    PdfOcrProcessingError,
)
from arabic_pdf_md_agent.base.schemas import (
    DocumentExtractionResult,
    ExtractionConfig,
    PageExtractionResult,
    RunSummary,
)

from .api import ocr_directory, ocr_pdf

__version__ = "0.1.0"

__all__ = [
    "ArabicPdfMdCoordinator",
    "DocumentExtractionResult",
    "ExtractionConfig",
    "PageExtractionResult",
    "PdfOcrDependencyError",
    "PdfOcrError",
    "PdfOcrExternalServiceError",
    "PdfOcrInputError",
    "PdfOcrProcessingError",
    "RunSummary",
    "__version__",
    "ocr_directory",
    "ocr_pdf",
    "run_extraction",
]

