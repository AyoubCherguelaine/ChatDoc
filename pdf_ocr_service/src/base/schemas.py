from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from arabic_pdf_md_agent.base.pricing import (
    DEFAULT_INPUT_COST_USD_PER_1M_TOKENS,
    DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS,
)


@dataclass(slots=True)
class ExtractionConfig:
    input_dir: Path
    output_dir: Path
    api_key: str
    input_pdf: Path | None = None
    model: str = "gemini-3.5-flash"
    dpi: int = 260
    include_glob: str = "*.pdf"
    recursive: bool = False
    max_pages_per_pdf: int | None = None
    document_chunk_page_count: int = 12
    overwrite: bool = False
    gemini_document_first: bool = True
    review_pass: bool = True
    max_attempts_per_page: int = 3
    min_page_arabic_chars: int = 40
    prefer_fallback_for_weak_pages: bool = True
    request_timeout_seconds: int = 90
    gemini_client_max_retries: int = 2
    gemini_client_retry_backoff_seconds: float = 1.25
    inter_request_delay_seconds: float = 0.2
    fail_fast: bool = False
    enable_usage_json_log: bool = True
    usage_log_path: Path | None = None
    input_cost_usd_per_1m_tokens: float = DEFAULT_INPUT_COST_USD_PER_1M_TOKENS
    output_cost_usd_per_1m_tokens: float = DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS


@dataclass(slots=True)
class PageExtractionResult:
    page_number: int
    markdown: str = ""
    draft_markdown: str | None = None
    status: str = "pending"
    attempts: int = 0
    error: str | None = None
    arabic_char_count: int = 0


@dataclass(slots=True)
class DocumentExtractionResult:
    pdf_path: Path
    md_path: Path | None = None
    status: str = "pending"
    total_pages: int = 0
    processed_pages: int = 0
    elapsed_ms: int = 0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    page_results: list[PageExtractionResult] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class RunSummary:
    total_pdfs: int = 0
    success_pdfs: int = 0
    failed_pdfs: int = 0
    skipped_pdfs: int = 0
    total_pages: int = 0
    processed_pages: int = 0
    elapsed_ms: int = 0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


def dataclass_to_json(value: Any) -> Any:
    """Convert nested dataclasses and Paths into JSON-serializable values."""
    if hasattr(value, "__dataclass_fields__"):
        raw = asdict(value)
        return dataclass_to_json(raw)
    if isinstance(value, dict):
        return {key: dataclass_to_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [dataclass_to_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value
