#!/usr/bin/env python3
"""Root-level entrypoint for the Arabic PDF OCR pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from arabic_pdf_md_agent.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
