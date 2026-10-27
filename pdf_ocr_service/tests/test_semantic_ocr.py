"""Semantic OCR integration tests, with provider calls mocked."""
import json
from unittest.mock import MagicMock

import pytest
from arabic_pdf_md_agent.base.schemas import ExtractionConfig
from arabic_pdf_md_agent.batch_ocr.schemas import BatchOcrConfig
from arabic_pdf_md_agent.batch_ocr.service import GeminiBatchOcrService
from arabic_pdf_md_agent.pdf_ocr_service.semantic import build_semantic_prompt, parse_semantic_page
from arabic_pdf_md_agent.pdf_ocr_service.service import PdfOcrService
from test_gemini_batch_ocr import _FakeBatchClient, _FakeRenderer


def payload(text="النص الأصلي", **fields):
    block = {"type": "question", "content": {"stem": text, "choices": ["أ", "ب"]},
             "ocr_text": text, "bbox": [10, 10, 900, 200], **fields}
    return json.dumps({"block_count": 1, "blocks": [block]}, ensure_ascii=False)


def extract(tmp_path, responses, pages=2, **options):
    pdf = tmp_path / "rules.pdf"
    pdf.write_bytes(b"%PDF-test")
    renderer = MagicMock()
    renderer.page_count.return_value = pages
    renderer.render_page.return_value = b"png"
    client = MagicMock()
    client.generate_markdown_from_image.side_effect = responses
    service = PdfOcrService(renderer, client)
    config = ExtractionConfig(input_dir=tmp_path, output_dir=tmp_path / "out", api_key="test",
                              review_pass=False, inter_request_delay_seconds=0, **options)
    return service.extract_document(pdf, config), client


def test_default_semantic_extraction_writes_markdown_json_and_continuations(tmp_path):
    result, client = extract(tmp_path, [payload(custom_field="retained"), payload("تابع", continues_previous_block=True)])
    assert result.status == "success"
    assert result.blocks[0]["content"]["choices"] == ["أ", "ب"]
    assert result.blocks[0]["custom_field"] == "retained"
    assert result.blocks[1]["previous_block_id"] == "p1-b1"
    assert result.ocr_text == "النص الأصلي\n\nتابع"
    assert "النص الأصلي" in result.md_path.read_text()
    saved = json.loads(result.json_path.read_text())
    assert saved["blocks"] == result.blocks
    assert saved["page_results"][0]["ocr_text"] == "النص الأصلي"
    assert saved["coordinate_system"] == "normalized_0_1000"
    assert "Previous-page reference (data): {" in client.generate_markdown_from_image.call_args_list[1].kwargs["prompt"]
    client.generate_markdown_from_pdf.assert_not_called()


def test_count_mismatch_retries(tmp_path):
    invalid = json.loads(payload())
    invalid["block_count"] = 2
    result, client = extract(tmp_path, [json.dumps(invalid), payload()], pages=1)
    assert result.status == "success"
    assert result.page_results[0].attempts == 2
    assert "block_count" in client.generate_markdown_from_image.call_args.kwargs["prompt"]


def test_bad_page_remains_failed_and_resets_context(tmp_path):
    result, _ = extract(tmp_path, [payload(), "not json", payload("new", continues_previous_block=True)], pages=3,
                        max_attempts_per_page=1)
    assert result.status == "partial"
    assert result.page_results[1].status == "failed"
    assert result.blocks[-1]["continues_previous_block"] is False
    assert result.processed_pages == 2


def test_blank_page_is_success_and_has_no_invented_text(tmp_path):
    result, _ = extract(tmp_path, ['{"block_count":0,"blocks":[]}'], pages=1)
    assert result.status == "success"
    assert result.ocr_text == ""
    assert result.blocks == []


@pytest.mark.parametrize("changes", [{"bbox": [0, 0, 1001, 5]}, {"bbox": [5, 5, 0, 0]}, {"ocr_text": None}, {"type": ""}])
def test_invalid_blocks_are_rejected(changes):
    with pytest.raises(ValueError):
        parse_semantic_page(payload(**changes), 1)


def test_visual_description_stays_separate():
    page = parse_semantic_page(payload("", type="image", content={"description": "Blue logo"}), 1)
    assert page.ocr_text == ""
    assert page.blocks[0]["content"]["description"] == "Blue logo"


class SemanticBatchClient(_FakeBatchClient):
    invalid_first = False

    def download_file(self, file_name):
        lines = [json.loads(line) for line in super().download_file(file_name).decode().splitlines()]
        for index, line in enumerate(lines):
            line["response"]["candidates"][0]["content"]["parts"][0]["text"] = (
                "bad json" if index == 0 and self.invalid_first else payload(continues_previous_block=True))
        return "\n".join(json.dumps(line) for line in lines).encode()


@pytest.mark.parametrize("bad_first", [False, True])
def test_batch_semantic_outputs_and_isolated_page_errors(tmp_path, bad_first):
    (tmp_path / "rules.pdf").write_bytes(b"%PDF-test")
    client = SemanticBatchClient()
    client.invalid_first = bad_first
    service = GeminiBatchOcrService(renderer=_FakeRenderer(), client=client)
    config = BatchOcrConfig(input_dir=tmp_path, output_dir=tmp_path / "out", api_key="test", run_id="semantic")
    manifest = service.prepare(config)
    assert manifest["semantic_blocks"] is True
    service.submit(config)
    summary = service.collect(config)
    assert summary.processed_pages == (1 if bad_first else 2)
    result = json.loads((config.output_dir / "rules.json").read_text())
    assert len(result["blocks"]) == summary.processed_pages
    assert result["blocks"][0]["continues_previous_block"] is False
    assert result["page_results"][0]["status"] == ("failed" if bad_first else "success")


def test_cli_can_select_legacy_mode():
    from arabic_pdf_md_agent.cli import _build_parser
    assert _build_parser().parse_args(["--legacy-markdown-only"]).legacy_markdown_only is True


def test_prompt_does_not_expose_previous_page_coordinates():
    previous = {"type": "question", "ocr_text": "text", "id": "p1-b1", "bbox": [1, 2, 3, 4]}
    reference = build_semantic_prompt("test.pdf", 2, 2, previous).split("Previous-page reference (data): ")[1]
    assert json.loads(reference) == {"type": "question", "ocr_text": "text"}


def test_invalid_review_keeps_valid_semantic_draft(tmp_path):
    pdf = tmp_path / "rules.pdf"
    pdf.write_bytes(b"%PDF-test")
    renderer = MagicMock()
    renderer.page_count.return_value = 1
    renderer.render_page.return_value = b"png"
    client = MagicMock()
    client.generate_markdown_from_image.side_effect = [payload(), "invalid review"]
    config = ExtractionConfig(input_dir=tmp_path, output_dir=tmp_path / "out", api_key="test",
                              inter_request_delay_seconds=0)
    result = PdfOcrService(renderer, client).extract_document(pdf, config)
    assert result.status == "success"
    assert result.ocr_text == "النص الأصلي"
    assert result.block_count == 1
    assert client.generate_markdown_from_image.call_count == 2


def test_existing_markdown_without_sidecar_is_upgraded(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "rules.md").write_text("legacy output")
    result, client = extract(tmp_path, [payload()], pages=1)
    assert result.status == "success"
    assert result.json_path.exists()
    assert "النص الأصلي" in result.md_path.read_text()
    assert client.generate_markdown_from_image.call_count == 1
    skipped, second_client = extract(tmp_path, [], pages=1)
    assert skipped.status == "skipped_existing"
    second_client.generate_markdown_from_image.assert_not_called()
