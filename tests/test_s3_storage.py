"""Verify S3 operations, error handling, and public URL signing without Docker."""
import io
from urllib.parse import parse_qs, urlsplit

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from backend.storage import S3StorageService


@pytest.fixture
def service():
    return S3StorageService(endpoint="http://storage.internal:8333",
                            public_endpoint="https://objects.example.com",
                            access_key="test-key", secret_key="test-secret", bucket="documents")


def test_upload_and_read(service):
    raw = io.BytesIO(b"pdf-content")
    body = StreamingBody(raw, len(b"pdf-content"))
    with Stubber(service._client) as stub:
        stub.add_response("put_object", {}, {"Bucket": "documents", "Key": "a.pdf",
                          "Body": b"pdf-content", "ContentType": "application/pdf"})
        stub.add_response("get_object", {"Body": body}, {"Bucket": "documents", "Key": "a.pdf"})
        stub.add_response("delete_object", {}, {"Bucket": "documents", "Key": "a.pdf"})
        assert service.upload("a.pdf", b"pdf-content", "application/pdf") == "s3://documents/a.pdf"
        assert service.get_bytes("a.pdf") == b"pdf-content"
        assert service.delete("a.pdf")
        stub.assert_no_pending_responses()
    assert raw.closed


def test_exists_missing_and_access_denied(service):
    with Stubber(service._client) as stub:
        stub.add_client_error("head_object", service_error_code="404", http_status_code=404)
        stub.add_client_error("head_object", service_error_code="AccessDenied", http_status_code=403)
        assert not service.exists("missing.pdf")
        with pytest.raises(ClientError):
            service.exists("private.pdf")


def test_unavailable_storage_does_not_fall_back_to_disk(service, monkeypatch):
    def unavailable(**kwargs):
        raise EndpointConnectionError(endpoint_url=service.endpoint)
    monkeypatch.setattr(service._client, "put_object", unavailable)
    monkeypatch.setattr(service._client, "head_bucket", unavailable)
    assert not service.is_healthy()
    with pytest.raises(EndpointConnectionError):
        service.upload("a.pdf", b"data")


def test_url_signs_browser_endpoint(service):
    url = urlsplit(service.get_presigned_url("documents/report with spaces.pdf", 600))
    params = parse_qs(url.query)
    assert url.netloc == "objects.example.com"
    assert url.path == "/documents/documents/report%20with%20spaces.pdf"
    assert params["X-Amz-Expires"] == ["600"]
    assert params["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert "X-Amz-Signature" in params


@pytest.mark.parametrize("name", ["", "/absolute", "../escape"])
def test_invalid_object_name(service, name):
    with pytest.raises(ValueError):
        service.upload(name, b"data")


def test_ingestion_reports_storage_failure(tmp_path, monkeypatch):
    from backend import rag
    from backend.config import settings
    from backend.storage import storage_service

    source = tmp_path / "source.txt"
    source.write_text("A readable document")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "INDEX_DIR", str(tmp_path / "indexes"))

    def unavailable(*args, **kwargs):
        raise EndpointConnectionError(endpoint_url=storage_service.endpoint)

    monkeypatch.setattr(storage_service, "upload", unavailable)
    with pytest.raises(EndpointConnectionError):
        rag.process_upload("user-test", source, "source.txt", source.stat().st_size, "text/plain")
    assert list((tmp_path / "uploads").iterdir()) == []
