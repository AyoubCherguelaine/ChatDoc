from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arabic_pdf_md_agent.agent import ArabicPdfMdCoordinator
from arabic_pdf_md_agent.base.prompts import normalize_model_markdown
from arabic_pdf_md_agent.base.errors import PdfOcrError
from arabic_pdf_md_agent.base.schemas import DocumentExtractionResult, ExtractionConfig, RunSummary
from arabic_pdf_md_agent.pdf_ocr_service.agent import PdfOcrDomainAgent


class _FakeDomainAgent:
    def __init__(self) -> None:
        self.called = False

    def run(self, config: ExtractionConfig):
        self.called = True
        self.config = config
        return [], RunSummary(total_pdfs=1, success_pdfs=1)


class CoordinatorTests(unittest.TestCase):
    def test_coordinator_routes_to_domain_agent(self) -> None:
        fake = _FakeDomainAgent()
        coordinator = ArabicPdfMdCoordinator(domain_agent=fake)
        config = ExtractionConfig(
            input_dir=Path("output/pdfs"),
            output_dir=Path("output/arabic_md"),
            api_key="test-key",
        )

        _, summary = coordinator.run(config)

        self.assertTrue(fake.called)
        self.assertEqual(summary.total_pdfs, 1)
        self.assertEqual(summary.success_pdfs, 1)

    def test_markdown_normalizer_unwraps_fence(self) -> None:
        wrapped = "```markdown\n# عنوان\nنص\n```"
        self.assertEqual(normalize_model_markdown(wrapped), "# عنوان\nنص")

    def test_direct_domain_agent_routes_single_input_pdf_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "pdfs"
            output_dir = root / "out"
            input_dir.mkdir()
            selected_pdf = input_dir / "selected.pdf"
            other_pdf = input_dir / "other.pdf"
            selected_pdf.write_bytes(b"%PDF-selected")
            other_pdf.write_bytes(b"%PDF-other")
            seen_paths: list[Path] = []

            class _FakeService:
                def __init__(self, renderer, gemini_client) -> None:
                    pass

                def extract_document(self, pdf_path: Path, config: ExtractionConfig) -> DocumentExtractionResult:
                    seen_paths.append(pdf_path)
                    return DocumentExtractionResult(
                        pdf_path=pdf_path,
                        md_path=output_dir / f"{pdf_path.stem}.md",
                        status="success",
                        total_pages=1,
                        processed_pages=1,
                    )

            config = ExtractionConfig(
                input_pdf=selected_pdf,
                input_dir=input_dir,
                output_dir=output_dir,
                api_key="test-key",
            )

            with (
                patch("arabic_pdf_md_agent.pdf_ocr_service.agent.GeminiVisionClient"),
                patch("arabic_pdf_md_agent.pdf_ocr_service.agent.PdfRenderer"),
                patch("arabic_pdf_md_agent.pdf_ocr_service.agent.PdfOcrService", _FakeService),
            ):
                _, summary = PdfOcrDomainAgent().run(config)

            self.assertEqual(seen_paths, [selected_pdf])
            self.assertEqual(summary.total_pdfs, 1)
            self.assertEqual(summary.success_pdfs, 1)

    def test_domain_agent_continues_after_one_pdf_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "pdfs"
            output_dir = root / "out"
            input_dir.mkdir()
            first_pdf = input_dir / "broken.pdf"
            second_pdf = input_dir / "good.pdf"
            first_pdf.write_bytes(b"%PDF-broken")
            second_pdf.write_bytes(b"%PDF-good")
            seen_paths: list[Path] = []

            class _FailOnceService:
                def __init__(self, renderer, gemini_client) -> None:
                    pass

                def extract_document(self, pdf_path: Path, config: ExtractionConfig) -> DocumentExtractionResult:
                    seen_paths.append(pdf_path)
                    if pdf_path == first_pdf:
                        raise PdfOcrError("forced failure")
                    return DocumentExtractionResult(
                        pdf_path=pdf_path,
                        md_path=output_dir / f"{pdf_path.stem}.md",
                        status="success",
                        total_pages=1,
                        processed_pages=1,
                    )

            config = ExtractionConfig(
                input_dir=input_dir,
                output_dir=output_dir,
                api_key="test-key",
            )

            with (
                patch("arabic_pdf_md_agent.pdf_ocr_service.agent.GeminiVisionClient"),
                patch("arabic_pdf_md_agent.pdf_ocr_service.agent.PdfRenderer"),
                patch("arabic_pdf_md_agent.pdf_ocr_service.agent.PdfOcrService", _FailOnceService),
            ):
                results, summary = PdfOcrDomainAgent().run(config)

            self.assertEqual(seen_paths, [first_pdf, second_pdf])
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].status, "failed")
            self.assertEqual(results[1].status, "success")
            self.assertEqual(summary.total_pdfs, 2)
            self.assertEqual(summary.failed_pdfs, 1)
            self.assertEqual(summary.success_pdfs, 1)


if __name__ == "__main__":
    unittest.main()
