from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from arabic_pdf_md_agent.base.schemas import ExtractionConfig
from arabic_pdf_md_agent.pdf_ocr_service.service import PdfOcrService


class _DummyRenderer:
    def __init__(self) -> None:
        self.retry_dpis: list[int] = []

    def iter_selected_pages(
        self,
        pdf_path: Path,
        dpi: int,
        page_numbers: set[int],
        max_pages: int | None = None,
    ):
        for page_number in sorted(page_numbers):
            yield page_number, f"base-{page_number}".encode("utf-8")

    def render_page(
        self,
        pdf_path: Path,
        page_number: int,
        dpi: int,
        max_pages: int | None = None,
    ) -> bytes:
        self.retry_dpis.append(dpi)
        return f"retry-{page_number}-{dpi}".encode("utf-8")


class _DummyChunker:
    def make_chunk_bytes(self, pdf_path: Path, start_page: int, end_page: int) -> bytes:
        return f"chunk-{start_page}-{end_page}".encode("utf-8")


class _ReviewFailsButDraftWorksClient:
    def __init__(self) -> None:
        self.image_calls = 0

    def generate_markdown_from_image(self, prompt: str, image_bytes: bytes, log_context=None) -> str:
        self.image_calls += 1
        if self.image_calls == 1:
            return "نص عربي صالح"
        raise RuntimeError("review exploded")

    def generate_markdown_from_pdf(self, prompt: str, pdf_bytes: bytes, log_context=None) -> str:
        raise RuntimeError("not used")


class _ImageFailsPdfRescuesClient:
    def __init__(self) -> None:
        self.image_calls = 0
        self.pdf_calls = 0

    def generate_markdown_from_image(self, prompt: str, image_bytes: bytes, log_context=None) -> str:
        self.image_calls += 1
        raise RuntimeError("image OCR failed")

    def generate_markdown_from_pdf(self, prompt: str, pdf_bytes: bytes, log_context=None) -> str:
        self.pdf_calls += 1
        return "<!-- PAGE: 1 -->\nنص من إنقاذ PDF"


class _DocReviewFailsClient:
    def __init__(self) -> None:
        self.calls = 0

    def generate_markdown_from_image(self, prompt: str, image_bytes: bytes, log_context=None) -> str:
        raise RuntimeError("not used")

    def generate_markdown_from_pdf(self, prompt: str, pdf_bytes: bytes, log_context=None) -> str:
        self.calls += 1
        if self.calls == 1:
            return "<!-- PAGE: 1 -->\nنص الصفحة"
        raise RuntimeError("document review failed")


class _ChunkFailureClient:
    def generate_markdown_from_image(self, prompt: str, image_bytes: bytes, log_context=None) -> str:
        page_number = (log_context or {}).get("page_number", "?")
        return f"نص صفحة {page_number} من fallback"

    def generate_markdown_from_pdf(self, prompt: str, pdf_bytes: bytes, log_context=None) -> str:
        if "Extract only source pages 1 to 2" in prompt:
            raise RuntimeError("chunk timeout")
        if "Extract only source pages 3 to 4" in prompt:
            return "<!-- PAGE: 3 -->\nنص 3\n<!-- PAGE: 4 -->\nنص 4"
        return ""


class _BrokenRenderer:
    def page_count(self, pdf_path: Path) -> int:
        raise RuntimeError("pdfium exploded")


class _DummyGeminiClient:
    def generate_markdown_from_image(self, prompt: str, image_bytes: bytes, log_context=None) -> str:
        return "dummy"

    def generate_markdown_from_pdf(self, prompt: str, pdf_bytes: bytes, log_context=None) -> str:
        return "dummy"


class PageRecoveryStrategyTests(unittest.TestCase):
    def _config(self, **overrides) -> ExtractionConfig:
        payload = {
            "input_dir": Path("output/pdfs"),
            "output_dir": Path("output/arabic_md"),
            "api_key": "test-key",
            "review_pass": True,
            "max_attempts_per_page": 3,
            "inter_request_delay_seconds": 0,
        }
        payload.update(overrides)
        return ExtractionConfig(**payload)

    def test_page_review_failure_keeps_draft(self) -> None:
        renderer = _DummyRenderer()
        client = _ReviewFailsButDraftWorksClient()
        service = PdfOcrService(renderer=renderer, gemini_client=client, chunker=_DummyChunker())

        results = service._extract_with_page_images(
            pdf_path=Path("dummy.pdf"),
            page_limit=1,
            target_pages={1},
            config=self._config(max_attempts_per_page=1, review_pass=True),
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "success")
        self.assertEqual(results[0].markdown, "نص عربي صالح")

    def test_single_page_pdf_rescue_after_image_failures(self) -> None:
        renderer = _DummyRenderer()
        client = _ImageFailsPdfRescuesClient()
        service = PdfOcrService(renderer=renderer, gemini_client=client, chunker=_DummyChunker())

        results = service._extract_with_page_images(
            pdf_path=Path("dummy.pdf"),
            page_limit=1,
            target_pages={1},
            config=self._config(max_attempts_per_page=2, review_pass=False, dpi=220),
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "success")
        self.assertIn("نص من إنقاذ PDF", results[0].markdown)
        self.assertEqual(client.image_calls, 2)
        self.assertGreaterEqual(client.pdf_calls, 1)
        self.assertEqual(renderer.retry_dpis, [270])

    def test_document_review_failure_keeps_document_draft(self) -> None:
        service = PdfOcrService(
            renderer=_DummyRenderer(),
            gemini_client=_DocReviewFailsClient(),
            chunker=_DummyChunker(),
        )
        config = self._config(review_pass=True, max_attempts_per_page=1)

        results = service._extract_document_chunk(
            pdf_path=Path("dummy.pdf"),
            total_pages=1,
            start_page=1,
            end_page=1,
            config=config,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "success")
        self.assertEqual(results[0].page_number, 1)
        self.assertEqual(results[0].markdown, "نص الصفحة")

    def test_document_first_continues_when_one_chunk_fails(self) -> None:
        service = PdfOcrService(
            renderer=_DummyRenderer(),
            gemini_client=_ChunkFailureClient(),
            chunker=_DummyChunker(),
        )
        config = self._config(review_pass=False, document_chunk_page_count=2)

        results = service._extract_document_first_chunked(
            pdf_path=Path("dummy.pdf"),
            total_pages=4,
            page_limit=4,
            config=config,
        )
        by_page = {item.page_number: item for item in results}

        self.assertEqual(len(results), 4)
        self.assertEqual(by_page[1].status, "success")
        self.assertEqual(by_page[2].status, "success")
        self.assertEqual(by_page[3].status, "success")
        self.assertEqual(by_page[4].status, "success")
        self.assertIn("fallback", by_page[1].markdown)
        self.assertIn("fallback", by_page[2].markdown)

    def test_renderer_failure_is_reported_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_pdf = Path(tmpdir) / "bad.pdf"
            bad_pdf.write_bytes(b"%PDF-1.7")

            output_dir = Path(tmpdir) / "out"
            config = self._config(output_dir=output_dir)
            service = PdfOcrService(renderer=_BrokenRenderer(), gemini_client=_DummyGeminiClient())

            result = service.extract_document(pdf_path=bad_pdf, config=config)

            self.assertEqual(result.status, "failed")
            self.assertIn("Failed to inspect PDF", result.error or "")


if __name__ == "__main__":
    unittest.main()
