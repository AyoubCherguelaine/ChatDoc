from __future__ import annotations

import unittest
from pathlib import Path

from arabic_pdf_md_agent.base.schemas import ExtractionConfig, PageExtractionResult
from arabic_pdf_md_agent.pdf_ocr_service.service import PdfOcrService


class _DummyRenderer:
    pass


class _DummyGeminiClient:
    pass


class MergeQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PdfOcrService(renderer=_DummyRenderer(), gemini_client=_DummyGeminiClient())

    def test_merge_prefers_stronger_fallback_when_enabled(self) -> None:
        config = ExtractionConfig(
            input_dir=Path("output/pdfs"),
            output_dir=Path("output/arabic_md"),
            api_key="x",
            prefer_fallback_for_weak_pages=True,
        )
        doc = [PageExtractionResult(page_number=1, status="success", markdown="نص", arabic_char_count=2)]
        fb = [PageExtractionResult(page_number=1, status="success", markdown="نص عربي أطول بكثير", arabic_char_count=14)]

        merged = self.service._merge_results(doc, fb, page_limit=1, config=config)
        self.assertEqual(merged[0].arabic_char_count, 14)

    def test_merge_keeps_document_when_quality_override_disabled(self) -> None:
        config = ExtractionConfig(
            input_dir=Path("output/pdfs"),
            output_dir=Path("output/arabic_md"),
            api_key="x",
            prefer_fallback_for_weak_pages=False,
        )
        doc = [PageExtractionResult(page_number=1, status="success", markdown="نص", arabic_char_count=2)]
        fb = [PageExtractionResult(page_number=1, status="success", markdown="نص عربي أطول بكثير", arabic_char_count=14)]

        merged = self.service._merge_results(doc, fb, page_limit=1, config=config)
        self.assertEqual(merged[0].arabic_char_count, 2)

    def test_merge_fills_missing_pages(self) -> None:
        config = ExtractionConfig(
            input_dir=Path("output/pdfs"),
            output_dir=Path("output/arabic_md"),
            api_key="x",
        )
        merged = self.service._merge_results([], [], page_limit=2, config=config)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].status, "failed")
        self.assertEqual(merged[1].status, "failed")

    def test_merge_penalizes_many_unreadable_tokens(self) -> None:
        config = ExtractionConfig(
            input_dir=Path("output/pdfs"),
            output_dir=Path("output/arabic_md"),
            api_key="x",
            prefer_fallback_for_weak_pages=True,
        )
        noisy = PageExtractionResult(
            page_number=1,
            status="success",
            markdown="المادة الأولى [غير واضح] [غير واضح] [غير واضح]",
            arabic_char_count=30,
        )
        cleaner = PageExtractionResult(
            page_number=1,
            status="success",
            markdown="المادة الأولى تنظم أحكام العمل",
            arabic_char_count=25,
        )

        merged = self.service._merge_results([noisy], [cleaner], page_limit=1, config=config)
        self.assertEqual(merged[0].markdown, cleaner.markdown)


if __name__ == "__main__":
    unittest.main()
