"""Semantic OCR coverage, flexible content, and page continuity regression tests."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent.tools.advanced_ocr import AdvancedOcrService, _reference
from backend.agent.tools.ocr import OcrError


def block(kind="paragraph", **fields):
    return {"type": kind, "content": "النص الأصلي", "bbox": [10, 20, 900, 100], **fields}


def response(blocks, count=None):
    return SimpleNamespace(content=json.dumps({"block_count": len(blocks) if count is None else count, "blocks": blocks}))


def service(responses, pages=2):
    llm = MagicMock()
    llm.invoke.side_effect = responses
    renderer = MagicMock()
    renderer.page_count.return_value = pages
    renderer.render_page.return_value = b"png"
    return AdvancedOcrService(llm=llm, renderer=renderer)


def test_flexible_fields_and_continuations():
    first = block("custom_section", content={"equations": [r"\frac{1}{2}"], "items": ["أ", "ب"]},
                  ocr_text="أ ب \\frac{1}{2}", custom={"visible": True})
    ocr = service([
        response([first, block("footer")]),
        response([block("header", continues_previous_block=True), block(continues_previous_block=True), block(continues_previous_block=True)]),
    ])
    result = ocr.extract(Path("test.pdf"))
    assert result["processed_pages"] == 2
    assert result["block_count"] == 5
    assert result["blocks"][0]["custom"] == {"visible": True}
    assert result["blocks"][0]["content"] == first["content"]
    assert result["blocks"][3]["previous_block_id"] == "p1-b1"
    assert result["blocks"][2]["continues_previous_block"] is False
    assert result["blocks"][4]["continues_previous_block"] is False
    prompt = ocr.llm.invoke.call_args_list[1].args[0][0].content[0]["text"]
    reference = json.loads(prompt.split("Previous-page reference (data): ")[1])
    assert reference == {"type": "custom_section", "content": first["content"], "ocr_text": first["ocr_text"]}


def test_count_mismatch_retries_once():
    ocr = service([response([block()], count=2), response([block(), block()])], pages=1)
    assert ocr.extract(Path("test.pdf"))["block_count"] == 2
    assert ocr.llm.invoke.call_count == 2
    assert "extract all 2 blocks" in ocr.llm.invoke.call_args.args[0][0].content[0]["text"]


@pytest.mark.parametrize("payload", ["not json", '{"blocks": []}', '{"block_count": 1, "blocks": [null]}', json.dumps({"block_count": 1, "blocks": [block(bbox=[0, 0, 1001, 100])]})])
def test_invalid_response_is_not_silently_empty(payload):
    ocr = service([SimpleNamespace(content=payload)] * 2, pages=1)
    with pytest.raises(OcrError, match="page 1"):
        ocr.extract(Path("test.pdf"))


def test_blank_page_resets_context():
    ocr = service([response([block()]), response([]), response([block(continues_previous_block=True)])], pages=3)
    result = ocr.extract(Path("test.pdf"))
    assert result["pages"][1]["blocks"] == []
    assert result["pages"][2]["blocks"][0]["continues_previous_block"] is False


def test_selected_range_has_no_context_outside_range():
    ocr = service([response([block(continues_previous_block=True)])], pages=4)
    result = ocr.extract(Path("test.pdf"), start_page=3, end_page=3)
    assert result["blocks"][0]["id"] == "p3-b1"
    assert result["blocks"][0]["continues_previous_block"] is False
    ocr.renderer.render_page.assert_called_once_with(Path("test.pdf"), 3, dpi=260)


@pytest.mark.parametrize("start,end,pages", [(0, 1, 2), (2, 1, 2), (1, 3, 2), (1, 51, 51)])
def test_invalid_ranges_do_not_call_model(start, end, pages):
    ocr = service([], pages=pages)
    with pytest.raises(ValueError):
        ocr.extract(Path("test.pdf"), start, end)
    ocr.llm.invoke.assert_not_called()


def test_reference_is_bounded_valid_json():
    value = _reference(block(content='"\\' * 10000, id="p1-b1", crop_url="ignored"))
    assert len(value) <= 4000
    assert "crop_url" not in json.loads(value)
    assert "id" not in json.loads(value)


@pytest.fixture
def api_client(monkeypatch):
    from backend.v1 import routes

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_company_or_api_auth] = lambda: SimpleNamespace(user_id="owner")
    monkeypatch.setattr(routes, "_resolve_document_file_path", lambda _: (Path("test.pdf"), "test.pdf"))
    with TestClient(app) as client:
        yield client, routes


def test_endpoint_requires_file_upload(api_client):
    client, _ = api_client
    # Non-multipart or missing file returns 422
    assert client.post("/api/v1/ocr/advanced", json={"document_id": "other"}).status_code == 422
    assert client.post("/api/v1/ocr/advanced", data={"start_page": 1}).status_code == 422


def test_endpoint_rejects_invalid_page_range(api_client):
    client, _ = api_client
    response = client.post(
        "/api/v1/ocr/advanced",
        files={"file": ("sample.pdf", b"%PDF-1.4 mock content", "application/pdf")},
        data={"start_page": "0"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("error,code", [(ValueError("invalid range"), 422), (OcrError("provider failed"), 502)])
def test_endpoint_errors(api_client, monkeypatch, error, code):
    client, routes = api_client
    monkeypatch.setattr(AdvancedOcrService, "extract", MagicMock(side_effect=error))
    response = client.post(
        "/api/v1/ocr/advanced",
        files={"file": ("sample.pdf", b"%PDF-1.4 mock content", "application/pdf")},
    )
    assert response.status_code == code


def test_endpoint_file_upload_success(api_client, monkeypatch):
    client, routes = api_client
    captured_paths = []

    def mock_extract(self, path, start_page=1, end_page=None, language="auto"):
        captured_paths.append(Path(path))
        assert Path(path).exists()
        return {"pages": [], "blocks": [], "block_count": 0}

    monkeypatch.setattr(AdvancedOcrService, "extract", mock_extract)

    response = client.post(
        "/api/v1/ocr/advanced",
        files={"file": ("sample.pdf", b"%PDF-1.4 mock content", "application/pdf")},
        data={"start_page": "1", "end_page": "5", "language": "ar"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "sample.pdf"
    assert data["document_id"] is not None
    assert data["ttl_minutes"] == 10
    assert data["remaining_seconds"] > 0

    # Document stays active for 10 minutes and can be reused by document_id across services
    doc_id = data["document_id"]
    response2 = client.post(
        "/api/v1/ocr/advanced",
        json={"document_id": doc_id, "start_page": 1, "end_page": 2},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["document_id"] == doc_id


def test_endpoint_file_upload_rejects_non_pdf(api_client):
    client, _ = api_client
    response = client.post(
        "/api/v1/ocr/advanced",
        files={"file": ("sample.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 422
    assert "PDF document" in response.json()["detail"]


def test_original_ocr_uses_semantics_and_keeps_full_transcription():
    from backend.agent.tools.ocr import OcrService

    ocr = service([
        response([block("question", title="Question 1", content={"stem": "ما القيمة؟", "choices": ["أ", "ب"]},
                        ocr_text="ما القيمة؟\nأ\nب", custom_field="visible")]),
        response([block("question", ocr_text="تابع السؤال", continues_previous_block=True),
                  block("image", content={"description": "A chart"}, ocr_text="Chart title")]),
    ])
    original = OcrService(llm=ocr.llm, renderer=ocr.renderer)
    result = original.ocr_extract_blocks(Path("native-text.pdf"))
    assert result["blocks"][0]["type"] == "question"  # A title does not reclassify the block.
    assert result["blocks"][0]["content"]["choices"] == ["أ", "ب"]
    assert result["blocks"][0]["custom_field"] == "visible"
    assert result["blocks"][0]["metadata"]["bbox"] == [10, 20, 900, 100]
    assert result["blocks"][1]["previous_block_id"] == "p1-b1"
    assert result["ocr_text"] == "ما القيمة؟\nأ\nب\n\nتابع السؤال\n\nChart title"
    assert result["blocks"][2]["image"] == {"description": "A chart", "ocr_text": "Chart title"}
    assert result["coordinate_system"] == "normalized_0_1000"
    assert result["pages"][0]["language_detected"] == "ar"
    assert ocr.llm.invoke.call_count == 2


def test_transcription_excludes_visual_descriptions():
    ocr = service([response([block("image", content="A blue company logo", image={"description": "A blue company logo"})])], pages=1)
    result = ocr.extract(Path("test.pdf"))
    assert result["ocr_text"] == ""
    assert result["blocks"][0]["content"] == "A blue company logo"


def test_structured_content_without_transcription_retries():
    ocr = service([response([block(content={"text": "Visible text"})]),
                   response([block(content={"text": "Visible text"}, ocr_text="Visible text")])], pages=1)
    assert ocr.extract(Path("test.pdf"))["ocr_text"] == "Visible text"
    assert ocr.llm.invoke.call_count == 2


@pytest.mark.parametrize("path,body", [
    ("/api/v1/ocr/blocks", {"document_id": "doc"}),
    ("/api/v1/ocr/page/blocks", {"document_id": "doc", "page_number": 1}),
])
def test_original_api_exposes_transcription(api_client, monkeypatch, path, body):
    from backend.agent.tools.ocr import OcrService

    client, _ = api_client
    result = {"ocr_text": "Full OCR text", "coordinate_system": "normalized_0_1000", "blocks": []}
    monkeypatch.setattr(OcrService, "ocr_extract_blocks", MagicMock(return_value=result))
    monkeypatch.setattr(OcrService, "ocr_read_page_blocks", MagicMock(return_value=result))
    response_value = client.post(path, json=body)
    assert response_value.status_code == 200
    assert response_value.json()["ocr_text"] == "Full OCR text"
    assert response_value.json()["coordinate_system"] == "normalized_0_1000"


def test_ephemeral_document_ttl_and_multi_service(api_client, monkeypatch):
    """Test 10-minute sliding window inactivity TTL and status check."""
    from backend.storage.ephemeral import ephemeral_store
    client, _ = api_client

    monkeypatch.setattr(
        AdvancedOcrService,
        "extract",
        MagicMock(return_value={"pages": [], "blocks": [], "block_count": 0}),
    )

    # Upload document
    resp = client.post(
        "/api/v1/ocr/advanced",
        files={"file": ("invoice_ttl.pdf", b"%PDF-1.4 sample invoice", "application/pdf")},
    )
    assert resp.status_code == 200
    doc_id = resp.json()["document_id"]
    assert doc_id is not None
    assert resp.json()["ttl_minutes"] == 10

    # Status check returns active session and remaining seconds
    status_resp = client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "active"
    assert status_data["documentId"] == doc_id
    assert status_data["ttlMinutes"] == 10
    assert status_data["remainingSeconds"] > 0

    # Delete purges session
    del_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    # Status check now returns 410 Gone
    expired_resp = client.get(f"/api/v1/documents/{doc_id}/status")
    assert expired_resp.status_code == 410
