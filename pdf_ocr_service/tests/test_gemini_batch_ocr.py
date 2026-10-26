from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from arabic_pdf_md_agent.batch_ocr.schemas import BatchOcrConfig
from arabic_pdf_md_agent.batch_ocr.service import GeminiBatchOcrService
from arabic_pdf_md_agent.batch_ocr.usage_db import GeminiUsageStore


class _FakeRenderer:
    def page_count(self, pdf_path: Path) -> int:
        return 2

    def iter_rendered_pages(self, pdf_path: Path, dpi: int, max_pages: int | None = None):
        limit = max_pages or 2
        for page_number in range(1, limit + 1):
            yield page_number, f"png-{page_number}".encode("utf-8")


class _FakeBatchClient:
    def __init__(self) -> None:
        self.uploaded_paths: list[Path] = []
        self.fake_batch_name = "batches/test-batch"

    def upload_file(self, path: Path, *, display_name: str, mime_type: str):
        self.uploaded_paths.append(path)
        if mime_type == "application/jsonl":
            return {"file": {"name": "files/requests-jsonl", "uri": "https://files/requests-jsonl"}}
        return {"file": {"name": f"files/{path.stem}", "uri": f"https://files/{path.stem}"}}

    def create_batch(self, batch_input_file_name: str, *, display_name: str):
        return {"name": self.fake_batch_name, "state": "JOB_STATE_PENDING"}

    def get_batch(self, batch_name: str):
        return {"name": batch_name, "state": "JOB_STATE_SUCCEEDED", "dest": {"fileName": "files/results-jsonl"}}

    def download_file(self, file_name: str) -> bytes:
        lines = [
            {
                "key": "rules__page_0001",
                "response": {
                    "candidates": [{"content": {"parts": [{"text": "نص الصفحة الأولى"}]}}],
                    "usageMetadata": {
                        "promptTokenCount": 1000,
                        "candidatesTokenCount": 200,
                        "thoughtsTokenCount": 25,
                        "totalTokenCount": 1225,
                    },
                },
            },
            {
                "key": "rules__page_0002",
                "response": {
                    "candidates": [{"content": {"parts": [{"text": "نص الصفحة الثانية"}]}}],
                    "usageMetadata": {
                        "promptTokenCount": 900,
                        "candidatesTokenCount": 100,
                        "totalTokenCount": 1000,
                    },
                },
            },
        ]
        return ("\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n").encode("utf-8")


class GeminiBatchUsageTests(unittest.TestCase):
    def test_usage_store_upserts_and_rebuilds_totals_without_double_counting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "usage.sqlite3"
            store = GeminiUsageStore(db_path)
            store.initialize()
            store.upsert_run(
                run_id="run-1",
                model="gemini-3.1-flash-image",
                input_dir=Path("input"),
                output_dir=Path("output"),
                status="prepared",
                input_price_per_1m_usd=1.5,
                output_price_per_1m_usd=9.0,
                total_pdfs=1,
                total_pages=1,
            )
            for _ in range(2):
                store.upsert_page_usage(
                    run_id="run-1",
                    request_key="doc__page_0001",
                    pdf_path="doc.pdf",
                    page_number=1,
                    status="success",
                    input_tokens=1000,
                    output_tokens=225,
                    total_tokens=1225,
                    estimated_cost_usd=0.003525,
                )

            store.rebuild_pdf_usage("run-1", {"doc.pdf": {"pdf_stem": "doc", "total_pages": 1}})
            totals = store.rebuild_run_totals("run-1", "collected")

            self.assertEqual(totals["input_tokens"], 1000)
            self.assertEqual(totals["output_tokens"], 225)
            self.assertAlmostEqual(totals["estimated_cost_usd"], 0.003525)

    def test_usage_calculation_includes_thought_tokens(self) -> None:
        usage = GeminiBatchOcrService.usage_from_response(
            {
                "usageMetadata": {
                    "promptTokenCount": 1000,
                    "candidatesTokenCount": 200,
                    "thoughtsTokenCount": 25,
                    "totalTokenCount": 1225,
                }
            },
            input_cost_usd_per_1m_tokens=1.50,
            output_cost_usd_per_1m_tokens=9.00,
        )

        self.assertEqual(usage.input_tokens, 1000)
        self.assertEqual(usage.output_tokens, 225)
        self.assertEqual(usage.total_tokens, 1225)
        self.assertAlmostEqual(usage.estimated_cost_usd, 0.003525)

    def test_parse_result_lines_handles_malformed_and_page_error(self) -> None:
        parsed = GeminiBatchOcrService.parse_result_lines(
            [
                '{"key": "ok", "response": {"candidates": []}}',
                '{"key": "bad", "error": {"message": "blocked"}}',
                '{"key": ',
            ]
        )

        self.assertIn("ok", parsed)
        self.assertEqual(parsed["bad"]["error"]["message"], "blocked")
        self.assertTrue(any(key.startswith("malformed:") for key in parsed))

    def test_mocked_batch_flow_writes_markdown_and_sqlite_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "pdfs"
            output_dir = root / "arabic_md"
            input_dir.mkdir()
            (input_dir / "rules.pdf").write_bytes(b"%PDF-test")

            config = BatchOcrConfig(
                input_dir=input_dir,
                output_dir=output_dir,
                api_key="test-key",
                run_id="run-1",
                input_cost_usd_per_1m_tokens=1.50,
                output_cost_usd_per_1m_tokens=9.00,
            )
            service = GeminiBatchOcrService(renderer=_FakeRenderer(), client=_FakeBatchClient())

            manifest = service.prepare(config)
            submitted = service.submit(config)
            status = service.status(config)
            summary = service.collect(config)

            self.assertEqual(manifest["run_id"], "run-1")
            self.assertEqual(submitted["batch_job_name"], "batches/test-batch")
            self.assertEqual(status["state"], "JOB_STATE_SUCCEEDED")
            self.assertEqual(summary.processed_pages, 2)
            self.assertEqual(summary.input_tokens, 1900)
            self.assertEqual(summary.output_tokens, 325)
            self.assertTrue((output_dir / "rules.md").exists())
            self.assertIn("نص الصفحة الأولى", (output_dir / "rules.md").read_text(encoding="utf-8"))

            conn = sqlite3.connect(output_dir / "gemini_usage.sqlite3")
            try:
                page_count = conn.execute("SELECT COUNT(*) FROM page_usage").fetchone()[0]
                pdf_row = conn.execute("SELECT input_tokens, output_tokens FROM pdf_usage").fetchone()
            finally:
                conn.close()
            self.assertEqual(page_count, 2)
            self.assertEqual(pdf_row, (1900, 325))

    def test_prepare_with_input_pdf_only_queues_selected_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "pdfs"
            output_dir = root / "arabic_md"
            input_dir.mkdir()
            selected_pdf = input_dir / "rules.pdf"
            other_pdf = input_dir / "other.pdf"
            selected_pdf.write_bytes(b"%PDF-rules")
            other_pdf.write_bytes(b"%PDF-other")

            config = BatchOcrConfig(
                input_pdf=selected_pdf,
                input_dir=input_dir,
                output_dir=output_dir,
                api_key="test-key",
                run_id="run-1",
            )
            service = GeminiBatchOcrService(renderer=_FakeRenderer(), client=_FakeBatchClient())

            manifest = service.prepare(config)

            self.assertEqual(manifest["input_pdf"], str(selected_pdf))
            self.assertEqual([Path(item["pdf_path"]) for item in manifest["documents"]], [selected_pdf])
            self.assertEqual({Path(item["pdf_path"]) for item in manifest["pages"]}, {selected_pdf})

    def test_batch_run_returns_noop_summary_when_pdf_is_skipped_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_dir = root / "pdfs"
            output_dir = root / "arabic_md"
            input_dir.mkdir()
            output_dir.mkdir()
            selected_pdf = input_dir / "rules.pdf"
            selected_pdf.write_bytes(b"%PDF-rules")
            (output_dir / "rules.md").write_text("already extracted", encoding="utf-8")

            config = BatchOcrConfig(
                input_pdf=selected_pdf,
                input_dir=input_dir,
                output_dir=output_dir,
                api_key="test-key",
                run_id="run-skip",
            )
            service = GeminiBatchOcrService(renderer=_FakeRenderer(), client=_FakeBatchClient())

            result = service.run(config, wait=True)

            self.assertEqual(result.status, "skipped_existing")
            self.assertEqual(result.total_pdfs, 1)
            self.assertEqual(result.total_pages, 0)
            self.assertEqual(result.processed_pages, 0)


if __name__ == "__main__":
    unittest.main()
