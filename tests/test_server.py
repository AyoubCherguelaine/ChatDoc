"""API contract tests isolate model calls and enforce ownership before file access."""

import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from backend import server
from backend.auth import get_current_user

USER = {"id": str(uuid.uuid4()), "name": "Tester"}


@pytest.fixture
def client():
    server.app.dependency_overrides[get_current_user] = lambda: USER
    with TestClient(server.app) as client:
        yield client
    server.app.dependency_overrides.clear()


def test_capabilities_only_offer_configured_models(client):
    result = client.get("/api/capabilities").json()
    assert result["defaultModel"] in result["models"]
    assert {".pdf", ".docx", ".xlsx", ".xls"} <= set(result["formats"])
    assert result["maxUploadMB"] == 5
    assert result["maxPages"] == 3


def test_reject_unknown_model_before_saving_message(client, monkeypatch):
    monkeypatch.setattr(server, "query", lambda *a, **kw: {"document_id": "doc"})
    monkeypatch.setattr(server, "execute", lambda *a, **kw: pytest.fail("Should not persist"))
    response = client.post("/api/sessions/session/chat", json={"message": "Hello", "model": "not-enabled"})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "  "},
        {"message": ""},
        {"message": "Hi", "mode": "execute"},
        {"message": "Hi", "responseStyle": "unsafe"},
        {"message": "x" * 20001},
    ],
)
def test_invalid_chat_settings(client, monkeypatch, payload):
    monkeypatch.setattr(server, "query", lambda *a, **kw: {"document_id": "doc"})
    response = client.post("/api/sessions/session/chat", json=payload)
    assert response.status_code == 422


def test_chat_history_precedes_current_turn_and_options_reach_rag(client, monkeypatch):
    events = []
    monkeypatch.setattr(server, "query", lambda *a, **kw: {"document_id": "doc"})
    monkeypatch.setattr(server, "execute", lambda sql, params: events.append(("write", params)))

    def history(session):
        events.append(("history", session))
        return [AIMessage(content="Previous answer")]

    monkeypatch.setattr(server.rag, "get_history", history)

    def stream(**kwargs):
        assert kwargs["response_style"] == "detailed"
        assert kwargs["mode"] == "agent"
        assert len(kwargs["history"]) == 1
        yield "Grounded "
        yield "answer"

    monkeypatch.setattr(server.rag, "stream_chat", stream)
    response = client.post(
        "/api/sessions/session/chat",
        json={
            "message": "Question",
            "mode": "agent",
            "responseStyle": "detailed",
        },
    )
    assert response.text == "Grounded answer"
    assert events[0][0] == "history"
    assert events[-1][1][-1] == "Grounded answer"


def test_source_reader_checks_owner_before_opening_file(client, monkeypatch):
    monkeypatch.setattr(server, "query", lambda *a, **kw: None)
    response = client.get("/api/documents/other-users-document/pages/1")
    assert response.status_code == 404


def test_sessions_are_scoped_to_current_user(client, monkeypatch):
    def query(sql, params, **kwargs):
        assert params == (USER["id"], None, None)
        assert "s.user_id = %s" in sql
        return []

    monkeypatch.setattr(server, "query", query)
    assert client.get("/api/sessions").json() == []


def test_upload_rejects_unsupported_empty_and_oversize(client):
    for filename, content, status in [
        ("image.png", b"image", 400),
        ("empty.txt", b"", 413),
        ("large.txt", b"x" * (5 * 1024 * 1024 + 1), 413),
    ]:
        result = client.post("/api/documents/upload", files={"file": (filename, content)})
        assert result.status_code == status


def test_parse_failure_cleans_staged_files(tmp_path, monkeypatch):
    from backend import rag

    monkeypatch.setattr(rag.settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(rag.settings, "INDEX_DIR", str(tmp_path / "indexes"))
    source = tmp_path / "empty.txt"
    source.write_text(" ")
    with pytest.raises(ValueError, match="No readable"):
        rag.process_upload(USER["id"], source, "empty.txt", 1, "text/plain")
    assert list((tmp_path / "uploads").iterdir()) == []
    assert source.exists()


def test_settings_load_root_credentials_even_with_backend_env(tmp_path, monkeypatch):
    import runpy
    from pathlib import Path

    repo = tmp_path / "repo"
    backend = repo / "backend"
    backend.mkdir(parents=True)
    (repo / ".env").write_text("OPENAI_API_KEY=local-test-placeholder\n")
    (backend / ".env").write_text("DEBUG=1\n")
    config = backend / "config.py"
    config.write_text((Path(server.__file__).parent / "config.py").read_text())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.chdir(tmp_path)
    loaded = runpy.run_path(str(config))["settings"]
    assert loaded.OPENAI_API_KEY == "local-test-placeholder"
    assert loaded.DEBUG


def test_playground_presets(client):
    res = client.get("/api/playground/presets")
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert "invoice" in data["presets"]
    assert "contract" in data["presets"]
    assert "models" in data
    invoice_preset = data["presets"]["invoice"]
    assert "default_schema" in invoice_preset
    assert "sample_text" in invoice_preset
    assert "default_system_prompt" not in invoice_preset


def test_playground_run_with_sample_text(client, monkeypatch):
    from unittest.mock import MagicMock
    from backend.agent.agents.base import AgentResult

    mock_agent = MagicMock()
    mock_agent.run.return_value = AgentResult(
        response='{"invoice_number": "INV-2026-999", "total_amount": 500.0}',
        success=True,
        iterations=2,
        steps=[{"thought": "Parsing sample", "action": "none", "observation": "ok"}],
    )
    monkeypatch.setattr(server.rag, "_build_agent", lambda *a, **kw: mock_agent)

    payload = {
        "service": "invoice",
        "text_content": "Invoice INV-2026-999 Total: $500",
        "user_prompt": "Extract invoice fields",
        "schema_override": {"invoice_number": "str", "total_amount": "float"},
        "model": "gpt-4o",
    }
    res = client.post("/api/playground/run", json=payload)
    assert res.status_code == 200
    result = res.json()
    assert result["success"] is True
    assert result["service"] == "invoice"
    assert result["data"]["invoice_number"] == "INV-2026-999"
    assert result["data"]["total_amount"] == 500.0
    assert result["latencyMs"] >= 0
    assert "steps" in result

