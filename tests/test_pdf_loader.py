"""Tests for documents/pdf_loader.py"""

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.documents.pdf_loader import (
    PageText,
    PDFDocument,
    extract_page_text,
    extract_pages_text,
    load_pdf,
    load_pdfs,
)

# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestPageText:
    def test_page_text_creation(self):
        pt = PageText(page_number=1, text="Hello", doc_name="test.pdf", total_pages=3)
        assert pt.page_number == 1
        assert pt.text == "Hello"
        assert pt.doc_name == "test.pdf"
        assert pt.total_pages == 3

    def test_str_representation(self):
        pt = PageText(page_number=2, text="A" * 200, doc_name="doc.pdf", total_pages=5)
        s = str(pt)
        assert "doc.pdf" in s
        assert "p.2/5" in s

    def test_str_representation_short_text(self):
        pt = PageText(page_number=1, text="Hi", doc_name="doc.pdf", total_pages=1)
        s = str(pt)
        assert "..." in s


class TestPDFDocument:
    def _make_doc(self):
        pages = [
            PageText(1, "Page 1 text", "test.pdf", 3),
            PageText(2, "Page 2 text", "test.pdf", 3),
            PageText(3, "Page 3 text", "test.pdf", 3),
        ]
        return PDFDocument(name="test.pdf", pages=pages, file_path="/tmp/test.pdf")

    def test_total_pages(self):
        doc = self._make_doc()
        assert doc.total_pages == 3

    def test_get_page_in_range(self):
        doc = self._make_doc()
        page = doc.get_page(2)
        assert page is not None
        assert page.page_number == 2

    def test_get_page_out_of_range(self):
        doc = self._make_doc()
        assert doc.get_page(0) is None
        assert doc.get_page(4) is None
        assert doc.get_page(-1) is None

    def test_get_pages_range(self):
        doc = self._make_doc()
        pages = doc.get_pages(1, 2)
        assert len(pages) == 2
        assert pages[0].page_number == 1
        assert pages[1].page_number == 2

    def test_get_pages_partial_range(self):
        doc = self._make_doc()
        pages = doc.get_pages(2, 10)
        assert len(pages) == 2
        assert pages[0].page_number == 2
        assert pages[1].page_number == 3


# ---------------------------------------------------------------------------
# Loader tests (mocked)
# ---------------------------------------------------------------------------


class TestLoadPdf:
    @patch("backend.documents.pdf_loader.fitz")
    def test_load_pdf_with_pymupdf(self, mock_fitz):
        mock_doc = MagicMock()
        mock_doc.page_count = 2
        mock_doc.__iter__ = lambda self: iter(
            [
                MagicMock(
                    get_text=lambda *a, **kw: "This is the full text content of page one with sufficient length."
                ),
                MagicMock(
                    get_text=lambda *a, **kw: "This is the full text content of page two with sufficient length."
                ),
            ]
        )
        mock_doc.close = MagicMock()
        mock_fitz.open.return_value = mock_doc

        doc = load_pdf("/fake/test.pdf")
        assert doc.name == "test.pdf"
        assert doc.total_pages == 2
        assert "page one" in doc.pages[0].text
        assert "page two" in doc.pages[1].text
        assert doc.pages[0].page_number == 1

    @patch("backend.documents.pdf_loader.PdfReader")
    def test_load_pdf_fallback_pypdf(self, mock_reader):
        mock_page1 = MagicMock(extract_text=lambda: "P1")
        mock_page2 = MagicMock(extract_text=lambda: "P2")
        mock_reader.return_value.pages = [mock_page1, mock_page2]

        with patch("backend.documents.pdf_loader.fitz", None):
            doc = load_pdf("/fake/doc.pdf")
        assert doc.total_pages == 2
        assert doc.pages[0].text == "P1"

    def test_load_pdf_no_backend(self):
        with patch("backend.documents.pdf_loader.fitz", None):
            with patch("backend.documents.pdf_loader.PdfReader", None):
                with pytest.raises(ImportError, match="No PDF backend"):
                    load_pdf("/fake/doc.pdf")

    def test_load_pdfs_multiple(self):
        with patch("backend.documents.pdf_loader.load_pdf") as mock_load:
            mock_load.side_effect = lambda p: PDFDocument(
                name=os.path.basename(str(p)),
                pages=[PageText(1, "t", "d", 1)],
            )
            docs = load_pdfs(["/fake/a.pdf", "/fake/b.pdf"])
        assert len(docs) == 2


class TestExtractPageText:
    @patch("backend.documents.pdf_loader.load_pdf")
    def test_extract_page_text_valid(self, mock_load):
        mock_load.return_value.get_page.return_value.text = "Page content here"
        result = extract_page_text("/fake/doc.pdf", 1)
        assert result == "Page content here"

    @patch("backend.documents.pdf_loader.load_pdf")
    def test_extract_page_text_out_of_range(self, mock_load):
        mock_load.return_value.get_page.return_value = None
        mock_load.return_value.total_pages = 3
        with pytest.raises(ValueError, match="out of range"):
            extract_page_text("/fake/doc.pdf", 5)


class TestExtractPagesText:
    @patch("backend.documents.pdf_loader.load_pdf")
    def test_extract_pages_range(self, mock_load):
        doc = MagicMock()
        doc.get_pages.return_value = [
            PageText(1, "Text A", "doc.pdf", 3),
            PageText(2, "Text B", "doc.pdf", 3),
        ]
        mock_load.return_value = doc

        result = extract_pages_text("/fake/doc.pdf", 1, 2)
        assert "Text A" in result
        assert "Text B" in result

    @patch("backend.documents.pdf_loader.load_pdf")
    def test_extract_pages_none(self, mock_load):
        doc = MagicMock()
        doc.get_pages.return_value = []
        mock_load.return_value = doc

        with pytest.raises(ValueError, match="out of range"):
            extract_pages_text("/fake/doc.pdf", 5, 10)


class TestTableAndOcrPdfLoader:
    @patch("backend.documents.pdf_loader.fitz")
    def test_load_pdf_with_tables(self, mock_fitz):
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Here is some introductory text that is long enough to exceed eighty characters in length so that it does not trigger OCR fallback."

        mock_table = MagicMock()
        mock_table.extract.return_value = [
            ["Description", "Quantity", "Amount"],
            ["Consulting Services", "10", "$1500"],
            ["Hosting Setup", "1", "$250"],
        ]
        mock_tab_finder = MagicMock()
        mock_tab_finder.tables = [mock_table]
        mock_page.find_tables.return_value = mock_tab_finder

        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_fitz.open.return_value = mock_doc

        doc = load_pdf("/fake/invoice.pdf")
        assert len(doc.pages) == 1
        page = doc.pages[0]
        assert len(page.tables) == 1
        assert "| Description | Quantity | Amount |" in page.tables[0]
        assert "| Consulting Services | 10 | $1500 |" in page.tables[0]
        assert "### Extracted Tables" in page.text

    @patch("backend.agent.tools.ocr.OcrService.ocr_read_page")
    @patch("backend.documents.pdf_loader.fitz")
    def test_load_pdf_sparse_triggers_ocr(self, mock_fitz, mock_ocr_read):
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Scanned scan"
        mock_page.find_tables.return_value = None

        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_fitz.open.return_value = mock_doc

        mock_ocr_read.return_value = "### Invoice #1234\nClient: ACME Corp\nTotal: $500"

        doc = load_pdf("/fake/scanned_invoice.pdf")
        assert len(doc.pages) == 1
        page = doc.pages[0]
        assert page.is_ocr is True
        assert "Invoice #1234" in page.text
        assert mock_ocr_read.called

    @patch("backend.documents.pdf_loader.fitz")
    def test_load_pdf_extracts_structured_json(self, mock_fitz):
        mock_page = MagicMock()
        mock_page.get_text.return_value = (
            "Invoice Summary\n\n"
            "```json\n"
            "{\n"
            '  "invoice_number": "INV-2026-001",\n'
            '  "vendor": "Test Vendor",\n'
            '  "total_amount": 1250.00\n'
            "}\n"
            "```\n"
            "Thank you for your business!"
        )
        mock_page.find_tables.return_value = None

        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_fitz.open.return_value = mock_doc

        doc = load_pdf("/fake/invoice_with_json.pdf")
        assert doc.structured_data is not None
        assert doc.structured_data.get("invoice_number") == "INV-2026-001"
        assert doc.structured_data.get("vendor") == "Test Vendor"

