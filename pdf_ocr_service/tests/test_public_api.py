from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import pdf_llm_ocr
from arabic_pdf_md_agent.base.schemas import DocumentExtractionResult, RunSummary
from pdf_llm_ocr import api


def test_public_package_exports_stable_api() -> None:
    assert pdf_llm_ocr.__version__ == "0.1.0"
    assert callable(pdf_llm_ocr.ocr_pdf)
    assert callable(pdf_llm_ocr.ocr_directory)


def test_ocr_pdf_builds_config_and_returns_first_result(tmp_path: Path) -> None:
    pdf = tmp_path / "rules.pdf"
    pdf.write_bytes(b"%PDF-test")
    expected = DocumentExtractionResult(pdf_path=pdf, status="success")

    with patch.object(api, "run_extraction", return_value=([expected], RunSummary())) as run:
        result = api.ocr_pdf(
            pdf,
            tmp_path / "markdown",
            api_key="test-key",
            model="gemini-test",
            overwrite=True,
        )

    assert result is expected
    config = run.call_args.args[0]
    assert config.input_pdf == pdf
    assert config.api_key == "test-key"
    assert config.model == "gemini-test"
    assert config.overwrite is True


def test_ocr_directory_uses_environment_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")

    with patch.object(api, "run_extraction", return_value=([], RunSummary())) as run:
        api.ocr_directory(tmp_path, tmp_path / "markdown", recursive=True)

    config = run.call_args.args[0]
    assert config.api_key == "env-key"
    assert config.input_pdf is None
    assert config.recursive is True


def test_missing_api_key_has_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Gemini API key is required"):
        api.ocr_directory(tmp_path, tmp_path / "markdown")


def test_convenience_api_rejects_reserved_config_options(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="input_pdf"):
        api.ocr_directory(
            tmp_path,
            tmp_path / "markdown",
            api_key="test-key",
            input_pdf=tmp_path / "other.pdf",
        )
