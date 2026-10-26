from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from arabic_pdf_md_agent.agent import run_extraction
from arabic_pdf_md_agent.base.errors import PdfOcrError
from arabic_pdf_md_agent.base.pricing import load_project_pricing
from arabic_pdf_md_agent.base.schemas import ExtractionConfig
from arabic_pdf_md_agent.base.utils import configure_logging, load_env_files
from arabic_pdf_md_agent.batch_ocr.schemas import BatchOcrConfig
from arabic_pdf_md_agent.batch_ocr.service import GeminiBatchOcrService

DEFAULT_INPUT_DIR = Path("output/pdfs")
DEFAULT_OUTPUT_DIR = Path("output/arabic_md")


def _add_input_args(parser: argparse.ArgumentParser) -> None:
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--input-pdf", type=Path, default=None, help="Single PDF file to process.")
    input_group.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Directory containing PDF files. Defaults to output/pdfs when no input is provided.",
    )


def _resolved_input_dir(args: argparse.Namespace) -> Path:
    return args.input_dir or DEFAULT_INPUT_DIR


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-llm-ocr",
        description=(
            "Extract Arabic text from PDFs to Markdown using Gemini vision. "
            "Input defaults to output/pdfs and output defaults to output/arabic_md."
        ),
    )
    _add_input_args(parser)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory to write Markdown and manifests.")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), help="Gemini model name.")
    parser.add_argument("--dpi", type=int, default=260, help="Render DPI used before OCR.")
    parser.add_argument("--include-glob", default="*.pdf", help="Filename glob for selecting PDFs.")
    parser.add_argument("--recursive", action="store_true", help="Search for PDFs recursively in input dir.")
    parser.add_argument("--max-pages-per-pdf", type=int, default=None, help="Optional page cap per PDF.")
    parser.add_argument(
        "--document-chunk-page-count",
        type=int,
        default=12,
        help="Pages per Gemini document-first chunk. Lower for large PDFs.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Rewrite Markdown files even if they already exist.")
    parser.add_argument(
        "--disable-gemini-document-first",
        action="store_true",
        help="Disable Gemini PDF document-first mode and use page-image OCR only.",
    )
    parser.add_argument("--disable-review-pass", action="store_true", help="Disable second correction pass.")
    parser.add_argument("--max-attempts-per-page", type=int, default=3, help="Attempts per page before marking failure.")
    parser.add_argument(
        "--min-page-arabic-chars",
        type=int,
        default=40,
        help="Minimum Arabic characters expected per page before fallback OCR is preferred.",
    )
    parser.add_argument(
        "--disable-fallback-for-weak-pages",
        action="store_true",
        help="Do not trigger page-image fallback for weak document-first pages.",
    )
    parser.add_argument("--request-timeout-seconds", type=int, default=90, help="Gemini request timeout in seconds.")
    parser.add_argument(
        "--gemini-client-max-retries",
        type=int,
        default=2,
        help="Internal Gemini HTTP retries for transient timeout/rate-limit/server errors.",
    )
    parser.add_argument(
        "--gemini-client-retry-backoff-seconds",
        type=float,
        default=1.25,
        help="Linear backoff seconds multiplier between Gemini client retries.",
    )
    parser.add_argument("--inter-request-delay-seconds", type=float, default=0.2, help="Delay between model requests.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failed page in each PDF.")
    parser.add_argument(
        "--usage-log-path",
        type=Path,
        default=None,
        help="JSONL usage/cost log path. Defaults to <output-dir>/gemini_usage.jsonl.",
    )
    parser.add_argument(
        "--disable-usage-json-log",
        action="store_true",
        help="Disable the default Gemini usage/cost JSONL log.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser


def _add_batch_common_args(parser: argparse.ArgumentParser) -> None:
    _add_input_args(parser)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory to write Markdown, batch state, and usage DB.")
    parser.add_argument("--model", default=os.getenv("GEMINI_BATCH_MODEL", "gemini-3.1-flash-image"), help="Gemini batch model name.")
    parser.add_argument("--dpi", type=int, default=260, help="Render DPI used before OCR.")
    parser.add_argument("--include-glob", default="*.pdf", help="Filename glob for selecting PDFs.")
    parser.add_argument("--recursive", action="store_true", help="Search for PDFs recursively in input dir.")
    parser.add_argument("--max-pages-per-pdf", type=int, default=None, help="Optional page cap per PDF.")
    parser.add_argument("--overwrite", action="store_true", help="Rewrite Markdown files even if they already exist.")
    parser.add_argument("--usage-db-path", type=Path, default=None, help="SQLite usage DB path. Defaults to <output-dir>/gemini_usage.sqlite3.")
    parser.add_argument(
        "--input-cost-usd-per-1m-tokens",
        type=float,
        default=None,
        help="Input token price used for SQLite cost estimates. Defaults to project config.py pricing.",
    )
    parser.add_argument(
        "--output-cost-usd-per-1m-tokens",
        type=float,
        default=None,
        help="Output token price used for SQLite cost estimates. Defaults to project config.py pricing.",
    )
    parser.add_argument("--request-timeout-seconds", type=int, default=90, help="Gemini request timeout in seconds.")
    parser.add_argument("--run-id", default=None, help="Batch run id. Defaults to a new id for prepare/run, or latest run for submit/status/collect.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")


def _build_batch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-llm-ocr",
        description="Image-only Gemini Batch OCR for Arabic regulation PDFs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("batch-prepare", help="Render pages, upload images, and write batch JSONL.")
    _add_batch_common_args(prepare)

    submit = subparsers.add_parser("batch-submit", help="Upload batch JSONL and submit Gemini Batch job.")
    _add_batch_common_args(submit)

    status = subparsers.add_parser("batch-status", help="Fetch Gemini Batch job status.")
    _add_batch_common_args(status)

    collect = subparsers.add_parser("batch-collect", help="Download batch results, rebuild Markdown, and write SQLite usage.")
    _add_batch_common_args(collect)
    collect.add_argument("--allow-partial", action="store_true", help="Collect available results even if job state is not succeeded.")

    run = subparsers.add_parser("batch-run", help="Prepare, submit, and optionally wait/collect.")
    _add_batch_common_args(run)
    run.add_argument("--wait", action="store_true", help="Poll until terminal state and collect results.")
    run.add_argument("--poll-interval-seconds", type=int, default=30, help="Seconds between batch status polls.")
    run.add_argument("--allow-partial", action="store_true", help="Collect available results even if job state is not succeeded.")
    return parser


def _load_api_key(parser: argparse.ArgumentParser) -> str:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        parser.error("Set GEMINI_API_KEY (or GOOGLE_API_KEY) before running.")
    return api_key


def _batch_config_from_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> BatchOcrConfig:
    input_cost, output_cost = load_project_pricing()
    if args.input_cost_usd_per_1m_tokens is not None:
        input_cost = max(0.0, float(args.input_cost_usd_per_1m_tokens))
    if args.output_cost_usd_per_1m_tokens is not None:
        output_cost = max(0.0, float(args.output_cost_usd_per_1m_tokens))
    return BatchOcrConfig(
        input_dir=_resolved_input_dir(args),
        output_dir=args.output_dir,
        api_key=_load_api_key(parser),
        input_pdf=args.input_pdf,
        model=args.model,
        dpi=args.dpi,
        include_glob=args.include_glob,
        recursive=args.recursive,
        max_pages_per_pdf=args.max_pages_per_pdf,
        overwrite=args.overwrite,
        usage_db_path=args.usage_db_path,
        input_cost_usd_per_1m_tokens=input_cost,
        output_cost_usd_per_1m_tokens=output_cost,
        request_timeout_seconds=args.request_timeout_seconds,
        poll_interval_seconds=getattr(args, "poll_interval_seconds", 30),
        run_id=args.run_id,
        allow_partial=getattr(args, "allow_partial", False),
    )


def _run_batch_cli(argv: list[str]) -> int:
    parser = _build_batch_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    config = _batch_config_from_args(args, parser)
    service = GeminiBatchOcrService()

    try:
        if args.command == "batch-prepare":
            manifest = service.prepare(config)
            uploaded_pages = sum(1 for page in manifest.get("pages", []) if page.get("status") == "uploaded")
            failed_entries = sum(
                1
                for page in manifest.get("pages", [])
                if page.get("status") not in {"uploaded", "queued"} and page.get("status") is not None
            )
            failed_entries += sum(
                1
                for document in manifest.get("documents", [])
                if document.get("status") in {"invalid_pdf", "render_failed"}
            )
            print(
                "Gemini batch OCR prepared: "
                f"run_id={manifest['run_id']} "
                f"pages={len(manifest.get('pages', []))} "
                f"requests={uploaded_pages}"
            )
            return 0 if uploaded_pages > 0 and failed_entries == 0 else 1
        if args.command == "batch-submit":
            submitted = service.submit(config)
            print(
                "Gemini batch OCR submitted: "
                f"run_id={submitted['run_id']} batch_job_name={submitted['batch_job_name']}"
            )
            return 0
        if args.command == "batch-status":
            status = service.status(config)
            print(
                "Gemini batch OCR status: "
                f"run_id={status['run_id']} batch_job_name={status['batch_job_name']} state={status['state']}"
            )
            return 0
        if args.command == "batch-collect":
            summary = service.collect(config)
            print(
                "Gemini batch OCR collected: "
                f"run_id={summary.run_id} status={summary.status} "
                f"total_pdfs={summary.total_pdfs} processed_pages={summary.processed_pages} "
                f"failed_pages={summary.failed_pages} input_tokens={summary.input_tokens} "
                f"output_tokens={summary.output_tokens} estimated_cost_usd={summary.estimated_cost_usd:.6f}"
            )
            return 0 if summary.failed_pages == 0 or args.allow_partial else 1
        if args.command == "batch-run":
            result = service.run(config, wait=args.wait)
            if hasattr(result, "run_id"):
                print(
                    "Gemini batch OCR run collected: "
                    f"run_id={result.run_id} status={result.status} "
                    f"total_pdfs={result.total_pdfs} processed_pages={result.processed_pages} "
                    f"failed_pages={result.failed_pages} input_tokens={result.input_tokens} "
                    f"output_tokens={result.output_tokens} estimated_cost_usd={result.estimated_cost_usd:.6f}"
                )
                return 0 if result.failed_pages == 0 or args.allow_partial else 1
            print(
                "Gemini batch OCR run submitted: "
                f"run_id={result['run_id']} batch_job_name={result['batch_job_name']}"
            )
            return 0
        parser.error(f"Unsupported batch command: {args.command}")
        return 2
    except PdfOcrError as error:
        print(f"OCR error: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # pragma: no cover - defensive umbrella
        print(f"Unexpected batch OCR error: {error}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    load_env_files(
        paths=[project_root / ".env"],
        override=False,
    )

    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].startswith("batch-"):
        return _run_batch_cli(argv)

    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    try:
        input_cost, output_cost = load_project_pricing()
        config = ExtractionConfig(
            input_dir=_resolved_input_dir(args),
            output_dir=args.output_dir,
            api_key=_load_api_key(parser),
            input_pdf=args.input_pdf,
            model=args.model,
            dpi=args.dpi,
            include_glob=args.include_glob,
            recursive=args.recursive,
            max_pages_per_pdf=args.max_pages_per_pdf,
            document_chunk_page_count=args.document_chunk_page_count,
            overwrite=args.overwrite,
            gemini_document_first=not args.disable_gemini_document_first,
            review_pass=not args.disable_review_pass,
            max_attempts_per_page=args.max_attempts_per_page,
            min_page_arabic_chars=args.min_page_arabic_chars,
            prefer_fallback_for_weak_pages=not args.disable_fallback_for_weak_pages,
            request_timeout_seconds=args.request_timeout_seconds,
            gemini_client_max_retries=args.gemini_client_max_retries,
            gemini_client_retry_backoff_seconds=args.gemini_client_retry_backoff_seconds,
            inter_request_delay_seconds=args.inter_request_delay_seconds,
            fail_fast=args.fail_fast,
            enable_usage_json_log=not args.disable_usage_json_log,
            usage_log_path=args.usage_log_path,
            input_cost_usd_per_1m_tokens=input_cost,
            output_cost_usd_per_1m_tokens=output_cost,
        )

        _, summary = run_extraction(config)

        print(
            "Arabic Markdown extraction finished: "
            f"total_pdfs={summary.total_pdfs} "
            f"success={summary.success_pdfs} "
            f"failed={summary.failed_pdfs} "
            f"skipped={summary.skipped_pdfs} "
            f"total_pages={summary.total_pages} "
            f"processed_pages={summary.processed_pages} "
            f"elapsed_ms={summary.elapsed_ms} "
            f"model_calls={summary.model_calls} "
            f"input_tokens={summary.input_tokens} "
            f"output_tokens={summary.output_tokens} "
            f"estimated_cost_usd={summary.estimated_cost_usd:.6f}"
        )
        if summary.total_pdfs == 0:
            print("No PDF inputs were found.", file=sys.stderr)
            return 1
        return 0 if summary.failed_pdfs == 0 else 1
    except PdfOcrError as error:
        print(f"OCR error: {error}", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Run failed: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # pragma: no cover - defensive umbrella
        print(f"Unexpected OCR error: {error}", file=sys.stderr)
        return 1
