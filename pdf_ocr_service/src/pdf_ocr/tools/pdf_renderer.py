from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

from arabic_pdf_md_agent.base.errors import PdfOcrDependencyError, PdfOcrProcessingError


class PdfRenderer:
    """Render PDF pages into PNG bytes for vision models."""

    @staticmethod
    def _pdfium_module():
        try:
            import pypdfium2 as pdfium  # type: ignore
        except ImportError as error:  # pragma: no cover - dependency/environment issue
            raise PdfOcrDependencyError(
                "Missing dependency 'pypdfium2'. Install requirements before running OCR."
            ) from error
        return pdfium

    @staticmethod
    def _open_document(pdf_path: Path):
        pdfium = PdfRenderer._pdfium_module()
        try:
            return pdfium.PdfDocument(str(pdf_path))
        except Exception as error:  # pragma: no cover - dependency/environment issue
            raise PdfOcrProcessingError(f"Failed to open PDF {pdf_path}: {error}") from error

    def page_count(self, pdf_path: Path) -> int:
        document = self._open_document(pdf_path)
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

    def iter_rendered_pages(
        self,
        pdf_path: Path,
        dpi: int,
        max_pages: int | None = None,
    ) -> Iterator[tuple[int, bytes]]:
        document = self._open_document(pdf_path)
        page_total = len(document)
        limit = min(page_total, max_pages) if max_pages else page_total
        scale = max(dpi, 72) / 72.0

        try:
            for page_idx in range(limit):
                page_number = page_idx + 1
                try:
                    page = document[page_idx]
                    yield (page_number, self._render_page_to_png(page=page, scale=scale))
                except Exception as error:  # pragma: no cover - dependency/environment issue
                    raise PdfOcrProcessingError(
                        f"Failed to render page {page_number} from {pdf_path}: {error}"
                    ) from error
        finally:
            document.close()

    def iter_selected_pages(
        self,
        pdf_path: Path,
        dpi: int,
        page_numbers: set[int],
        max_pages: int | None = None,
    ) -> Iterator[tuple[int, bytes]]:
        if not page_numbers:
            return

        document = self._open_document(pdf_path)
        page_total = len(document)
        limit = min(page_total, max_pages) if max_pages else page_total
        scale = max(dpi, 72) / 72.0

        try:
            valid_pages = sorted(page for page in page_numbers if 1 <= page <= limit)
            for page_number in valid_pages:
                try:
                    page = document[page_number - 1]
                    yield (page_number, self._render_page_to_png(page=page, scale=scale))
                except Exception as error:  # pragma: no cover - dependency/environment issue
                    raise PdfOcrProcessingError(
                        f"Failed to render page {page_number} from {pdf_path}: {error}"
                    ) from error
        finally:
            document.close()

    def render_page(
        self,
        pdf_path: Path,
        page_number: int,
        dpi: int,
        max_pages: int | None = None,
    ) -> bytes | None:
        for rendered_page, image_bytes in self.iter_selected_pages(
            pdf_path=pdf_path,
            dpi=dpi,
            page_numbers={page_number},
            max_pages=max_pages,
        ):
            if rendered_page == page_number:
                return image_bytes
        return None

    def render_pages(
        self,
        pdf_path: Path,
        dpi: int,
        max_pages: int | None = None,
    ) -> list[tuple[int, bytes]]:
        # Compatibility helper for callers that still expect an eager list.
        return list(self.iter_rendered_pages(pdf_path=pdf_path, dpi=dpi, max_pages=max_pages))
