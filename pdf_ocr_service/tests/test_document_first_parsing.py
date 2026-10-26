from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arabic_pdf_md_agent.base.schemas import DocumentExtractionResult, ExtractionConfig, PageExtractionResult
from arabic_pdf_md_agent.pdf_ocr_service.prompts import build_document_prompt, build_ocr_prompt
from arabic_pdf_md_agent.pdf_ocr_service.service import PdfOcrService


class _DummyRenderer:
    def page_count(self, pdf_path: Path) -> int:
        return 2


class _DummyGeminiClient:
    pass


class DocumentFirstParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PdfOcrService(renderer=_DummyRenderer(), gemini_client=_DummyGeminiClient())

    def test_split_document_markdown_pages(self) -> None:
        markdown = """<!-- PAGE: 1 -->\nالنص الأول\n\n<!-- PAGE: 2 -->\nالنص الثاني"""
        results = self.service._split_document_markdown_to_pages(markdown_text=markdown, expected_pages={1, 2})

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].page_number, 1)
        self.assertEqual(results[1].page_number, 2)
        self.assertEqual(results[0].status, "success")
        self.assertEqual(results[1].status, "success")

    def test_missing_marker_adds_failed_page(self) -> None:
        markdown = """<!-- PAGE: 1 -->\nمحتوى الصفحة الأولى"""
        results = self.service._split_document_markdown_to_pages(markdown_text=markdown, expected_pages={1, 2})

        by_page = {item.page_number: item for item in results}
        self.assertEqual(by_page[1].status, "success")
        self.assertEqual(by_page[2].status, "failed")

    def test_no_markers_assigns_first_expected_page(self) -> None:
        markdown = "نص بدون علامات صفحات"
        results = self.service._split_document_markdown_to_pages(markdown_text=markdown, expected_pages={2, 3})

        by_page = {item.page_number: item for item in results}
        self.assertEqual(by_page[2].status, "success")
        self.assertEqual(by_page[3].status, "failed")

    def test_pages_needing_fallback_for_weak_output(self) -> None:
        config = ExtractionConfig(
            input_dir=Path("output/pdfs"),
            output_dir=Path("output/arabic_md"),
            api_key="test-key",
            min_page_arabic_chars=25,
            prefer_fallback_for_weak_pages=True,
        )
        weak = PageExtractionResult(page_number=1, status="success", markdown="abc", arabic_char_count=0)
        strong = PageExtractionResult(page_number=2, status="success", markdown="نص عربي واضح ومتكامل", arabic_char_count=30)

        targets = self.service._pages_needing_fallback([weak, strong], page_limit=2, config=config)
        self.assertEqual(targets, {1})

    def test_review_result_that_drops_page_marker_is_rejected(self) -> None:
        draft = "<!-- PAGE: 1 -->\nنص الصفحة الأولى\n<!-- PAGE: 2 -->\nنص الصفحة الثانية"
        reviewed = "<!-- PAGE: 1 -->\nنص الصفحة الأولى"

        selected = self.service._pick_best_markdown(draft=draft, reviewed=reviewed)

        self.assertEqual(selected, draft)

    def test_review_result_that_drops_most_arabic_text_is_rejected(self) -> None:
        draft = "نص عربي طويل يحتوي على المادة الأولى والبند الثاني ورقم 1445 مع تفاصيل نظامية متعددة"
        reviewed = "نص مختصر"

        selected = self.service._pick_best_markdown(draft=draft, reviewed=reviewed)

        self.assertEqual(selected, draft)

    def test_invalid_pdf_short_circuit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_pdf = Path(tmpdir) / "bad.pdf"
            bad_pdf.write_text("<!DOCTYPE html><html></html>", encoding="utf-8")

            output_dir = Path(tmpdir) / "out"
            config = ExtractionConfig(
                input_dir=Path(tmpdir),
                output_dir=output_dir,
                api_key="test-key",
            )
            result = self.service.extract_document(pdf_path=bad_pdf, config=config)

            self.assertEqual(result.status, "invalid_pdf")
            self.assertIn("%PDF", result.error or "")

    def test_prompt_guardrails_keep_separate_lines(self) -> None:
        prompt = build_ocr_prompt(pdf_name="sample.pdf", page_number=1, total_pages=3)
        self.assertIn("\n- If a stamp/signature appears", prompt)
        self.assertNotIn("].- If a stamp/signature appears", prompt)

        document_prompt = build_document_prompt(pdf_name="sample.pdf", total_pages=3, page_start=1, page_end=2)
        self.assertIn("\n- Do not translate to English.", document_prompt)
        self.assertNotIn("].- Do not translate to English.", document_prompt)

    def test_compose_document_markdown_includes_run_metadata(self) -> None:
        result = DocumentExtractionResult(
            pdf_path=Path("/tmp/sample.pdf"),
            status="success",
            total_pages=2,
            processed_pages=2,
            elapsed_ms=1234,
            model_calls=4,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.012345,
            page_results=[
                PageExtractionResult(page_number=1, status="success", markdown="نص الصفحة الأولى"),
                PageExtractionResult(page_number=2, status="success", markdown="نص الصفحة الثانية"),
            ],
        )

        markdown = PdfOcrService._compose_document_markdown(pdf_path=Path("/tmp/sample.pdf"), result=result)

        self.assertIn("> Elapsed: 1234 ms", markdown)
        self.assertIn("> Model calls: 4", markdown)
        self.assertIn("> Tokens: 100 in / 50 out / 150 total", markdown)
        self.assertIn("> Estimated cost: $0.012345", markdown)


if __name__ == "__main__":
    unittest.main()
