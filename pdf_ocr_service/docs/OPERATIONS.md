# PDF OCR Operations

## Quick Run Paths

Minimal install:
```bash
python3 -m venv venv
./venv/bin/pip install -e .
```

Single PDF or folder:
```bash
export GEMINI_API_KEY="your-key"
./venv/bin/pdf-llm-ocr --input-dir output/pdfs --output-dir output/arabic_md
```

Batch OCR:
```bash
./venv/bin/pdf-llm-ocr batch-run --input-dir output/pdfs --output-dir output/arabic_md --wait
```

## Pipeline Logic

1. Input selection
- `src/arabic_pdf_md_agent/base/utils.py` resolves PDF inputs and output directories.

2. OCR execution
- `src/arabic_pdf_md_agent/pdf_ocr_service/service.py` runs sequential semantic page OCR by default, or the legacy document-first and fallback flow with `--legacy-markdown-only`.
- `src/arabic_pdf_md_agent/pdf_ocr_service/agent.py` coordinates rendering, prompting, and retries.

3. Batch OCR
- `src/arabic_pdf_md_agent/batch_ocr/service.py` prepares, submits, and collects batch jobs.
- `src/arabic_pdf_md_agent/batch_ocr/usage_db.py` records usage and cost estimates.

4. Persistence
- `src/arabic_pdf_md_agent/pdf_ocr_service/db/manifest_store.py` writes per-document manifests.
- `output/arabic_md/*.md` stores the Markdown transcription.
- `output/arabic_md/*.json` stores semantic blocks and full OCR text; failed/partial sidecars do not suppress reruns.
- `output/arabic_md/_manifests/*.json` stores document manifests.

## Failure Notes

- Missing `GEMINI_API_KEY`: export the key before running.
- Invalid PDF input: the pipeline rejects files without a real `%PDF-` signature.
- Rate limits or timeouts: rerun with a higher timeout or batch retry settings.
