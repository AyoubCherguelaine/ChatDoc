# pdf-llm-ocr

`pdf-llm-ocr` converts Arabic PDF documents into semantic JSON and Markdown with Google
Gemini. Install it from GitHub, run it as a command-line tool, or import it into
another Python project. Gemini is the only supported provider in version `0.1.x`.

## Features

- Semantic page blocks with flexible `content` and complete verbatim `ocr_text`.
- Sequential page OCR with continuation links and normalized block coordinates.
- Legacy PDF-first Markdown OCR with automatic page-image fallback remains available.
- Optional second Gemini review pass for transcription correction.
- Single-file, directory, recursive, and asynchronous batch workflows.
- JSON manifests and token/cost usage logs.
- Stable `pdf_llm_ocr` Python API and `pdf-llm-ocr` command.

## Semantic OCR output

Semantic OCR is enabled by default for the CLI, Python API, and new batch runs.
For each PDF the service writes `name.md`, `name.json`, and the existing
`_manifests/name.json`. The Python result includes `json_path`, `blocks`,
`block_count`, `ocr_text`, and `page_results`; each page has its own blocks and
transcription. Markdown remains a readable rendering of the OCR transcription.

Each block includes a stable `id`, free-form `type`, flexible JSON `content`,
verbatim `ocr_text`, page number, reading order, and `bbox` on a normalized
0–1000 canvas (`[left, top, right, bottom]`). Additional document-specific fields
are retained. Visual descriptions belong in `content`; `ocr_text` contains only
visible text. No image crops are produced.

Standard OCR processes pages sequentially and passes the final meaningful block
of the immediately preceding successful page as context. A continuation includes
`continues_previous_block: true` and `previous_block_id`. Blank or failed pages
reset that context. Independent block counts and JSON structure are validated;
invalid output retries up to `max_attempts_per_page`. The optional review pass
also validates JSON, retaining the valid draft if review fails.

Batch pages run independently: they return semantic blocks and OCR text, with no
cross-page continuation inference. The chosen mode is saved in the batch manifest
so collection uses the format requested at preparation. Invalid semantic responses
mark individual pages as failed while other results and usage records are retained.
Old manifests without a mode continue to use Markdown parsing.

Semantic mode uses page images; document-first/chunk options apply to legacy mode.
To select the previous pipeline, use `--legacy-markdown-only` or pass
`semantic_blocks=False` to `ocr_pdf`, `ocr_directory`, or `ExtractionConfig`.
`BatchOcrConfig` accepts the same field. Existing Markdown without a successful
semantic JSON sidecar is regenerated; complete pairs are skipped unless
`--overwrite` is set. Failed or partial semantic output is eligible for reruns.

```python
from pdf_llm_ocr import ocr_pdf

result = ocr_pdf("document.pdf", "output", review_pass=False)
print(result.ocr_text)
for block in result.blocks:
    print(block["type"], block["content"], block["ocr_text"])
```

## Requirements

- Python 3.10 or newer.
- A [Google Gemini API key](https://aistudio.google.com/app/apikey).
- Internet access while OCR is running.

## Install

### From GitHub

Install the latest version from the public standalone repository:

```bash
python -m pip install \
  "pdf-llm-ocr @ git+https://github.com/Clean-code-org/pdf-llm-ocr.git"
```

Pin production installations to a release tag or commit:

```bash
python -m pip install \
  "pdf-llm-ocr @ git+https://github.com/Clean-code-org/pdf-llm-ocr.git@v0.1.0"
```

Because the repository is public, GitHub authentication is not required.

### Local development

```bash
git clone https://github.com/Clean-code-org/pdf-llm-ocr.git
cd pdf-llm-ocr
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Configure Gemini

Set the key before using the CLI:

```bash
export GEMINI_API_KEY="your-api-key"
```

`GOOGLE_API_KEY` is accepted as a fallback. Python calls can instead pass
`api_key="..."`. The installed library does not automatically read the caller's
`.env`; load it with the host project or export the variable explicitly. Optional
defaults are shown in `.env.example`.

## Command line

One PDF:

```bash
pdf-llm-ocr --input-pdf documents/rules.pdf --output-dir output/markdown
```

A directory:

```bash
pdf-llm-ocr --input-dir documents --output-dir output/markdown --recursive
```

Equivalent module command:

```bash
python -m pdf_llm_ocr --input-pdf documents/rules.pdf --output-dir output/markdown
```

Common options:

```text
--model MODEL                     Gemini model (default: GEMINI_MODEL or gemini-2.5-flash)
--overwrite                       replace existing Markdown
--disable-review-pass             reduce cost and latency
--max-pages-per-pdf N             process only the first N pages
--document-chunk-page-count N     pages per PDF-first request
--dpi N                           fallback render resolution
--include-glob PATTERN            select directory inputs
--verbose                         enable debug logs
```

Run `pdf-llm-ocr --help` for all options.

### Gemini Batch API

For large offline jobs:

```bash
pdf-llm-ocr batch-run \
  --input-dir documents \
  --output-dir output/markdown \
  --wait
```

Long jobs can be controlled and resumed separately:

```bash
pdf-llm-ocr batch-prepare --input-dir documents --output-dir output/markdown
pdf-llm-ocr batch-submit --output-dir output/markdown --run-id RUN_ID
pdf-llm-ocr batch-status --output-dir output/markdown --run-id RUN_ID
pdf-llm-ocr batch-collect --output-dir output/markdown --run-id RUN_ID
```

## Python API

### One PDF

```python
from pdf_llm_ocr import ocr_pdf

result = ocr_pdf(
    "documents/rules.pdf",
    "output/markdown",
    overwrite=True,
)

print(result.status)
print(result.md_path)
print(result.estimated_cost_usd)
```

### A directory

```python
from pdf_llm_ocr import ocr_directory

documents, summary = ocr_directory(
    "documents",
    "output/markdown",
    recursive=True,
    include_glob="*.pdf",
)

print(summary.success_pdfs, summary.failed_pdfs)
for document in documents:
    print(document.pdf_path, document.status, document.error)
```

Both functions accept additional `ExtractionConfig` fields as keyword arguments.
Misspelled or unsupported options raise `TypeError` instead of being ignored.

### Full configuration control

```python
import os
from pathlib import Path

from pdf_llm_ocr import ExtractionConfig, run_extraction

config = ExtractionConfig(
    input_dir=Path("documents"),
    output_dir=Path("output/markdown"),
    api_key=os.environ["GEMINI_API_KEY"],
    model="gemini-2.5-flash",
    recursive=True,
    review_pass=True,
)

results, summary = run_extraction(config)
```

See [Python API reference](docs/PYTHON_API.md) for fields, return types, errors,
and integration guidance.

## Outputs and safe reruns

```text
output/markdown/
├── document-name.md
├── gemini_usage.jsonl
├── run_summary.json
└── _manifests/
    └── document-name.json
```

Batch runs also use `_batch/<run-id>/` and `gemini_usage.sqlite3`. Existing
Markdown is skipped by default. Pass `overwrite=True` or `--overwrite` only when
replacement is intentional.

Invalid PDFs are rejected, transient Gemini failures are retried, and partial
documents retain successful pages with failures recorded in the manifest.

## Development

```bash
python -m pytest -q
python -m build
```

The project uses the standard `src/` layout. `pdf_llm_ocr` is the public API;
`arabic_pdf_md_agent` and root-level `arabic_pdf_md.py` remain for compatibility.

When creating the standalone GitHub repository, place this directory's contents
at the repository root, push the `main` branch, and create a `v0.1.0` tag after
the tests pass. The pinned installation command above will then work unchanged.
