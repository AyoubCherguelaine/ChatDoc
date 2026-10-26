from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arabic_pdf_md_agent.pdf_ocr_service.tools.gemini_client import GeminiVisionClient


class _FakeResponse:
    status_code = 200
    text = "{}"

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "نص عربي"},
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 1000,
                "cachedContentTokenCount": 100,
                "candidatesTokenCount": 200,
                "totalTokenCount": 1225,
                "thoughtsTokenCount": 25,
            },
        }


class _FakeSession:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        return _FakeResponse()


class GeminiUsageLoggingTests(unittest.TestCase):
    def test_successful_call_writes_jsonl_usage_and_cost(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "gemini_usage.jsonl"
            client = GeminiVisionClient(
                api_key="test-key",
                model="gemini-2.5-flash",
                usage_log_path=log_path,
                input_cost_usd_per_1m_tokens=1.50,
                output_cost_usd_per_1m_tokens=9.00,
                cached_input_cost_usd_per_1m_tokens=0.30,
            )
            client.session = _FakeSession()

            text = client.generate_markdown_from_pdf(
                prompt="extract",
                pdf_bytes=b"%PDF-test",
                log_context={"phase": "document_first_draft", "pdf_name": "x.pdf"},
            )

            self.assertEqual(text, "نص عربي")
            summary = client.usage_summary()
            self.assertEqual(summary["model_calls"], 1)
            self.assertEqual(summary["input_tokens"], 1000)
            self.assertEqual(summary["output_tokens"], 225)
            self.assertEqual(summary["total_tokens"], 1225)
            self.assertAlmostEqual(summary["estimated_cost_usd"], 0.003405)

            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            event = json.loads(lines[0])
            self.assertEqual(event["event"], "gemini_request")
            self.assertEqual(event["model"], "gemini-2.5-flash")
            self.assertEqual(event["modality"], "pdf")
            self.assertEqual(event["phase"], "document_first_draft")
            self.assertEqual(event["input_tokens"], 1000)
            self.assertEqual(event["cached_tokens"], 100)
            self.assertEqual(event["billable_input_tokens"], 900)
            self.assertEqual(event["candidate_output_tokens"], 200)
            self.assertEqual(event["thoughts_tokens"], 25)
            self.assertEqual(event["output_tokens"], 225)
            self.assertAlmostEqual(event["estimated_cost_usd"], 0.003405)


if __name__ == "__main__":
    unittest.main()
