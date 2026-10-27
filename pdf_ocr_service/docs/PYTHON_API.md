# Python API reference

Use public imports from `pdf_llm_ocr`:

```python
from pdf_llm_ocr import (
    DocumentExtractionResult,
    ExtractionConfig,
    PageExtractionResult,
    RunSummary,
    ocr_directory,
    ocr_pdf,
    run_extraction,
)
```

Application code should not depend on `arabic_pdf_md_agent`; it remains only for
compatibility with the original pipeline.

## Convenience functions

### `ocr_pdf(pdf_path, output_dir, *, api_key=None, model=None, **options)`

Runs one file and returns `DocumentExtractionResult`. `pdf_path` and `output_dir`
accept strings or `Path` objects. The API key can be passed explicitly or read
from `GEMINI_API_KEY` / `GOOGLE_API_KEY`.

### `ocr_directory(input_dir, output_dir, *, api_key=None, model=None, **options)`

Returns `(results, summary)`: a list of `DocumentExtractionResult` plus one
`RunSummary`. Pass `recursive=True` to scan subdirectories.

## `ExtractionConfig`

Required low-level fields:

| Field | Type | Meaning |
|---|---|---|
| `input_dir` | `Path` | Directory scanned without `input_pdf`. |
| `output_dir` | `Path` | Markdown and metadata destination. |
| `api_key` | `str` | Gemini API key. |

Frequently used optional fields:

| Field | Default | Meaning |
|---|---:|---|
| `input_pdf` | `None` | Exact PDF; bypasses directory scanning. |
| `model` | `gemini-2.5-flash` | Gemini model, overridden by `GEMINI_MODEL`. |
| `dpi` | `260` | Page-image render resolution. |
| `include_glob` | `*.pdf` | Directory selection pattern. |
| `recursive` | `False` | Search subdirectories. |
| `max_pages_per_pdf` | `None` | Optional per-PDF page cap. |
| `document_chunk_page_count` | `12` | Pages per document-first request. |
| `overwrite` | `False` | Replace existing Markdown. |
| `gemini_document_first` | `True` | Try PDF input before page images. |
| `review_pass` | `True` | Ask Gemini to correct the draft. |
| `max_attempts_per_page` | `3` | Fallback attempt limit. |
| `min_page_arabic_chars` | `40` | Weak-page fallback threshold. |
| `request_timeout_seconds` | `90` | Gemini HTTP timeout. |
| `gemini_client_max_retries` | `2` | Transient failure retry count. |
| `fail_fast` | `False` | Stop a PDF after its first failed page. |
| `enable_usage_json_log` | `True` | Write usage events. |
| `usage_log_path` | `None` | Custom JSONL path. |

The `ExtractionConfig` dataclass is the source of truth for less common retry,
quality, delay, and cost-estimation fields.

## Semantic OCR

`semantic_blocks=True` is the default. Results contain `blocks`, `block_count`,
`ocr_text`, `coordinate_system`, and per-page equivalents in `page_results`.
`json_path` points to the semantic JSON sidecar alongside the existing Markdown.
Block `content` is free-form JSON; `ocr_text` is the complete visible transcription.
Coordinates are normalized to 0–1000. Pass `semantic_blocks=False` for the legacy
Markdown-only pipeline and its document-first/fallback options.

## Results

`DocumentExtractionResult` includes paths, status, page counts, elapsed time,
Gemini calls, token usage, cost estimate, page results, and an optional error.

Statuses include `success`, `partial`, `failed`, `invalid_pdf`, and
`skipped_existing`. `RunSummary` aggregates the same operational data for a run.

## Exceptions

- `PdfOcrError`: base OCR exception.
- `PdfOcrInputError`: invalid input.
- `PdfOcrDependencyError`: unavailable PDF dependency.
- `PdfOcrProcessingError`: PDF rendering or processing failure.
- `PdfOcrExternalServiceError`: Gemini failure.

Per-document operational failures are normally captured in the result so other
files can continue. Invalid function arguments and missing API keys raise
immediately.

Pin the Git commit in consuming projects, keep the API key in their secret
manager, write outputs outside installed package directories, and always inspect
`result.status`.

