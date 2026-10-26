# Arabic PDF extraction behavior

This document explains how `pdf-llm-ocr` turns Arabic PDFs into Markdown. For
installation and public API usage, start with the [README](../README.md) and
[Python API reference](PYTHON_API.md).

## OCR flow

For each PDF, the library:

1. validates the path, extension, and `%PDF-` file signature;
2. reads its page count and applies the optional page limit;
3. splits it into document chunks (12 pages by default);
4. sends each PDF chunk to Gemini with deterministic extraction instructions;
5. optionally asks Gemini to review and correct the draft;
6. checks page markers and Arabic character coverage;
7. renders only missing or weak pages to PNG and retries them with Gemini vision;
8. merges the best page result into one Markdown document; and
9. writes the Markdown, manifest, run summary, and usage log.

This hybrid design keeps document context while recovering pages that a single
large PDF request might miss.

## Accuracy and cost controls

Use a smaller `--document-chunk-page-count` when Gemini misses pages in large or
complex files. Increase `--dpi` for small or degraded scans. Increase
`--min-page-arabic-chars` when sparse output should trigger image fallback.

The review pass improves difficult transcription but adds a second request. Skip
it with `--disable-review-pass` or `review_pass=False` when speed and cost matter
more. Use `--disable-gemini-document-first` only when every page should use image
OCR.

Example:

```bash
pdf-llm-ocr \
  --input-pdf documents/rules.pdf \
  --output-dir output/markdown \
  --document-chunk-page-count 8 \
  --dpi 300 \
  --gemini-client-max-retries 3
```

## Page preservation

The prompt requires `<!-- PAGE: N -->` markers. The merge layer uses those
markers to retain ordering and detect omitted pages. A review response is rejected
when it removes markers, loses too much Arabic text, or replaces transcription
with commentary.

Successful draft text is retained when the optional review call fails. A page is
reported as failed only after its configured recovery attempts are exhausted.

## Usage accounting

Standard OCR appends one JSON object per Gemini event to
`<output-dir>/gemini_usage.jsonl`. It records the phase, PDF/page context, model
usage metadata, latency, response size, and estimated cost. Pricing can be set
with:

```bash
export GEMINI_INPUT_COST_USD_PER_1M_TOKENS=0.30
export GEMINI_OUTPUT_COST_USD_PER_1M_TOKENS=2.50
```

These values are estimates only; Google billing remains authoritative.

## Batch mode

Gemini Batch mode renders pages to images, uploads them, submits one request per
page, and later reconstructs the documents. Local state in
`<output-dir>/_batch/<run-id>/` makes submission and collection resumable. Batch
usage is stored in `<output-dir>/gemini_usage.sqlite3` with run-, PDF-, and
page-level records.
