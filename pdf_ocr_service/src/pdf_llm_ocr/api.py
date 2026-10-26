"""Convenience functions for embedding PDF OCR in another Python project."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from arabic_pdf_md_agent.agent import run_extraction
from arabic_pdf_md_agent.base.pricing import load_project_pricing
from arabic_pdf_md_agent.base.schemas import (
    DocumentExtractionResult,
    ExtractionConfig,
    RunSummary,
)

_DEFAULT_MODEL = "gemini-2.5-flash"


def _api_key(explicit_api_key: str | None) -> str:
    key = explicit_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError(
            "Gemini API key is required. Pass api_key=... or set GEMINI_API_KEY."
        )
    return key


def _config(
    *,
    input_dir: Path,
    output_dir: Path,
    input_pdf: Path | None,
    api_key: str | None,
    model: str | None,
    options: dict[str, Any],
) -> ExtractionConfig:
    reserved = {"input_dir", "output_dir", "input_pdf", "api_key", "model"}.intersection(options)
    if reserved:
        names = ", ".join(sorted(reserved))
        raise TypeError(f"These options are controlled by the function arguments: {names}")
    input_cost, output_cost = load_project_pricing()
    config_values: dict[str, Any] = {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "input_pdf": input_pdf,
        "api_key": _api_key(api_key),
        "model": model or os.getenv("GEMINI_MODEL", _DEFAULT_MODEL),
        "input_cost_usd_per_1m_tokens": input_cost,
        "output_cost_usd_per_1m_tokens": output_cost,
    }
    config_values.update(options)
    return ExtractionConfig(**config_values)


def ocr_pdf(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    api_key: str | None = None,
    model: str | None = None,
    **options: Any,
) -> DocumentExtractionResult:
    """Convert one PDF to Markdown and return its detailed result.

    ``options`` accepts any additional :class:`ExtractionConfig` field, such as
    ``overwrite=True``, ``review_pass=False``, or ``dpi=300``.
    """

    pdf = Path(pdf_path)
    config = _config(
        input_dir=pdf.parent,
        output_dir=Path(output_dir),
        input_pdf=pdf,
        api_key=api_key,
        model=model,
        options=options,
    )
    results, _ = run_extraction(config)
    if not results:
        raise RuntimeError(f"OCR produced no result for {pdf}")
    return results[0]


def ocr_directory(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    api_key: str | None = None,
    model: str | None = None,
    **options: Any,
) -> tuple[list[DocumentExtractionResult], RunSummary]:
    """Convert PDFs in a directory and return document results plus run summary.

    ``options`` accepts any additional :class:`ExtractionConfig` field, including
    ``recursive=True`` and ``include_glob="regulation-*.pdf"``.
    """

    source = Path(input_dir)
    config = _config(
        input_dir=source,
        output_dir=Path(output_dir),
        input_pdf=None,
        api_key=api_key,
        model=model,
        options=options,
    )
    return run_extraction(config)
