from __future__ import annotations


class PdfOcrError(RuntimeError):
    """Base class for OCR pipeline failures."""


class PdfOcrInputError(PdfOcrError):
    """Raised when the caller provides invalid or missing input."""


class PdfOcrDependencyError(PdfOcrError):
    """Raised when an optional runtime dependency is missing."""


class PdfOcrProcessingError(PdfOcrError):
    """Raised when a PDF cannot be rendered or processed."""


class PdfOcrExternalServiceError(PdfOcrError):
    """Raised when Gemini or another external service fails."""

