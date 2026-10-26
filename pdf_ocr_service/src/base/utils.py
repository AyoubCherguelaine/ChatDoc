from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def load_env_files(paths: list[Path], override: bool = False) -> None:
    """Load KEY=VALUE pairs from .env-style files into os.environ."""
    import os

    for path in paths:
        if not path.exists() or not path.is_file():
            continue

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue

            if len(value) >= 2 and (
                (value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))
            ):
                value = value[1:-1]

            if override or key not in os.environ:
                os.environ[key] = value


def safe_file_stem(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "document"


def list_pdfs(input_dir: Path, include_glob: str = "*.pdf", recursive: bool = False) -> list[Path]:
    if recursive:
        paths = sorted(input_dir.rglob(include_glob), key=lambda p: str(p))
    else:
        paths = sorted(input_dir.glob(include_glob), key=lambda p: str(p))
    return [path for path in paths if path.is_file()]


def resolve_pdf_inputs(
    *,
    input_pdf: Path | None,
    input_dir: Path,
    include_glob: str = "*.pdf",
    recursive: bool = False,
) -> list[Path]:
    """Resolve either one explicit PDF or a directory scan into deterministic PDF paths."""
    if input_pdf is not None:
        if not input_pdf.exists():
            raise FileNotFoundError(f"Input PDF does not exist: {input_pdf}")
        if not input_pdf.is_file():
            raise ValueError(f"Input PDF path is not a file: {input_pdf}")
        if input_pdf.suffix.lower() != ".pdf":
            raise ValueError(f"Input file must have a .pdf extension: {input_pdf}")
        return [input_pdf]

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise ValueError(f"Input directory path is not a directory: {input_dir}")
    return list_pdfs(input_dir, include_glob, recursive)


def count_arabic_characters(text: str) -> int:
    return len(_ARABIC_RE.findall(text))


def is_probably_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            header = handle.read(5)
    except OSError:
        return False
    return header.startswith(b"%PDF-")


def chunk_ranges(page_limit: int, chunk_size: int) -> list[tuple[int, int]]:
    if page_limit <= 0:
        return []
    safe_chunk_size = max(1, chunk_size)
    ranges: list[tuple[int, int]] = []
    start = 1
    while start <= page_limit:
        end = min(page_limit, start + safe_chunk_size - 1)
        ranges.append((start, end))
        start = end + 1
    return ranges


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
