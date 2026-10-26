from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from arabic_pdf_md_agent.base.utils import resolve_pdf_inputs
from arabic_pdf_md_agent.cli import _build_parser


class PdfInputSelectionTests(unittest.TestCase):
    def test_single_pdf_returns_exact_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "one.pdf"
            pdf_path.write_bytes(b"%PDF-test")

            selected = resolve_pdf_inputs(input_pdf=pdf_path, input_dir=Path(tmpdir) / "unused")

            self.assertEqual(selected, [pdf_path])

    def test_directory_mode_respects_include_glob(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            keep = root / "keep.pdf"
            skip = root / "skip.pdf"
            keep.write_bytes(b"%PDF-keep")
            skip.write_bytes(b"%PDF-skip")

            selected = resolve_pdf_inputs(input_pdf=None, input_dir=root, include_glob="keep*.pdf")

            self.assertEqual(selected, [keep])

    def test_recursive_directory_mode_includes_nested_pdfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nested = root / "nested"
            nested.mkdir()
            top_pdf = root / "a.pdf"
            nested_pdf = nested / "b.pdf"
            top_pdf.write_bytes(b"%PDF-a")
            nested_pdf.write_bytes(b"%PDF-b")

            selected = resolve_pdf_inputs(input_pdf=None, input_dir=root, recursive=True)

            self.assertEqual(selected, [top_pdf, nested_pdf])

    def test_missing_input_pdf_fails_clearly(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "Input PDF does not exist"):
            resolve_pdf_inputs(input_pdf=Path("missing.pdf"), input_dir=Path("unused"))

    def test_non_pdf_input_file_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            text_path = Path(tmpdir) / "notes.txt"
            text_path.write_text("not pdf", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, r"\.pdf extension"):
                resolve_pdf_inputs(input_pdf=text_path, input_dir=Path(tmpdir))

    def test_cli_rejects_input_pdf_and_input_dir_together(self) -> None:
        parser = _build_parser()

        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            parser.parse_args(["--input-pdf", "one.pdf", "--input-dir", "output/pdfs"])


if __name__ == "__main__":
    unittest.main()
