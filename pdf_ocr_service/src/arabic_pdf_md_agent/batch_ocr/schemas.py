from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arabic_pdf_md_agent.base.pricing import (
    DEFAULT_INPUT_COST_USD_PER_1M_TOKENS,
    DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS,
)


@dataclass(slots=True)
class BatchOcrConfig:
    input_dir: Path
    output_dir: Path
    api_key: str
    input_pdf: Path | None = None
    model: str = "gemini-3.1-flash-image"
    dpi: int = 260
    include_glob: str = "*.pdf"
    recursive: bool = False
    max_pages_per_pdf: int | None = None
    overwrite: bool = False
    usage_db_path: Path | None = None
    input_cost_usd_per_1m_tokens: float = DEFAULT_INPUT_COST_USD_PER_1M_TOKENS
    output_cost_usd_per_1m_tokens: float = DEFAULT_OUTPUT_COST_USD_PER_1M_TOKENS
    request_timeout_seconds: int = 90
    poll_interval_seconds: int = 30
    run_id: str | None = None
    allow_partial: bool = False
    semantic_blocks: bool = True


@dataclass(frozen=True, slots=True)
class UsageRecord:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class BatchCollectSummary:
    run_id: str
    status: str
    total_pdfs: int
    success_pdfs: int
    failed_pdfs: int
    partial_pdfs: int
    total_pages: int
    processed_pages: int
    failed_pages: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
