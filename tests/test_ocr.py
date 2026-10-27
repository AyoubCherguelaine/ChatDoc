"""Tests for the OCR tools integrated into the agent framework."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agent.agents.contract import ContractAgent
from backend.agent.agents.invoice import InvoiceAgent
from backend.agent.tools.enhanced import EnhancedDocumentKit
from backend.agent.tools.ocr import (
    OcrError,
    OcrService,
    PdfRenderer,
)


class TestPdfRenderer:
    def test_page_count_success(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 5
        mock_doc.close = MagicMock()

        mock_pdfium = MagicMock()
        mock_pdfium.PdfDocument.return_value = mock_doc

        with patch.dict("sys.modules", {"pypdfium2": mock_pdfium}):
            renderer = PdfRenderer()
            assert renderer.page_count(pdf) == 5

    def test_page_count_missing_dependency(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with patch.dict("sys.modules", {"pypdfium2": None}):
            renderer = PdfRenderer()
            with pytest.raises(OcrError, match="pypdfium2"):
                renderer.page_count(pdf)

    def test_render_page_out_of_range(self, tmp_path):
        pdf = tmp_path / "test.pdf"

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 3
        mock_doc.close = MagicMock()

        mock_pdfium = MagicMock()
        mock_pdfium.PdfDocument.return_value = mock_doc

        with patch.dict("sys.modules", {"pypdfium2": mock_pdfium}):
            renderer = PdfRenderer()
            result = renderer.render_page(pdf, page_number=10, dpi=72)
            assert result is None

    def test_render_pages(self, tmp_path):
        pdf = tmp_path / "test.pdf"

        mock_page = MagicMock()
        mock_bitmap = MagicMock()
        mock_image = MagicMock()
        mock_bitmap.to_pil.return_value = mock_image
        mock_page.render.return_value = mock_bitmap

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_doc.__getitem__ = lambda self, i: mock_page
        mock_doc.close = MagicMock()

        mock_pdfium = MagicMock()
        mock_pdfium.PdfDocument.return_value = mock_doc

        with patch.dict("sys.modules", {"pypdfium2": mock_pdfium}):
            renderer = PdfRenderer()
            results = renderer.render_pages(pdf, dpi=72)
            assert len(results) == 1
            assert results[0][0] == 1
            assert isinstance(results[0][1], bytes)


class TestOcrService:
    def test_init_defaults(self):
        service = OcrService()
        assert service.renderer is not None
        assert service.dpi == 260
        assert service.llm is None

    def test_ensure_llm_creates_from_env(self):
        service = OcrService(llm=None)

        mock_llm = MagicMock()
        with patch("backend.chat.chatWithVSDB.get_llm", return_value=mock_llm):
            result = service._ensure_llm()
            assert result is mock_llm

    def test_ensure_llm_uses_provided_llm(self):
        mock_llm = MagicMock()
        service = OcrService(llm=mock_llm)
        assert service._ensure_llm() is mock_llm

    def test_ensure_llm_raises_on_failure(self):
        service = OcrService(llm=None)
        with patch("backend.chat.chatWithVSDB.get_llm", side_effect=Exception("no API")):
            with pytest.raises(OcrError, match="Could not initialise"):
                service._ensure_llm()

    def test_ocr_read_page_not_found(self):
        mock_renderer = MagicMock()
        mock_renderer.render_page.return_value = None
        service = OcrService(llm=MagicMock(), renderer=mock_renderer)
        result = service.ocr_read_page(Path("fake.pdf"), 1)
        assert "ERROR" in result
        assert "not found" in result.lower()

    def test_ocr_read_page_success(self):
        mock_renderer = MagicMock()
        mock_renderer.render_page.return_value = b"fake-png-bytes"
        service = OcrService(llm=MagicMock(), renderer=mock_renderer)

        with patch.object(service, "_image_to_base64", return_value="base64data"):
            mock_response = MagicMock()
            mock_response.content = "Extracted text from invoice"
            service.llm.invoke.return_value = mock_response

            result = service.ocr_read_page(Path("test.pdf"), 1)
            assert "Extracted text" in result

    def test_ocr_extract_invoice_not_found(self):
        mock_renderer = MagicMock()
        mock_renderer.render_page.return_value = None
        mock_renderer.page_count.return_value = 0
        service = OcrService(llm=MagicMock(), renderer=mock_renderer)
        result = service.ocr_extract_invoice(Path("test.pdf"))
        assert "ERROR" in result

    def test_ocr_extract_contract_success(self):
        mock_renderer = MagicMock()
        mock_renderer.render_page.return_value = b"fake-png"
        mock_renderer.page_count.return_value = 1
        service = OcrService(llm=MagicMock(), renderer=mock_renderer)

        mock_response = MagicMock()
        mock_response.content = json.dumps({"is_contract": True, "parties": []})
        service.llm.invoke.return_value = mock_response

        with patch.object(service, "_image_to_base64", return_value="b64"):
            result = service.ocr_extract_contract(Path("test.pdf"))
            data = json.loads(result)
            assert data["is_contract"] is True

    def test_image_to_base64(self):
        service = OcrService()
        b64 = service._image_to_base64(b"test")
        import base64

        assert b64 == base64.b64encode(b"test").decode("ascii")


class TestOcrIntegrationWithKit:
    def test_enhanced_kit_has_ocr_methods(self):
        kit = EnhancedDocumentKit()
        assert hasattr(kit, "ocr_read_page")
        assert hasattr(kit, "ocr_extract_invoice")
        assert hasattr(kit, "ocr_extract_contract")

    def test_ocr_read_page_doc_not_found(self):
        kit = EnhancedDocumentKit()
        result = kit.ocr_read_page("nonexistent.pdf", 1)
        assert "ERROR" in result or "not found" in result.lower()

    def test_invoice_agent_registers_ocr_tools(self):
        kit = EnhancedDocumentKit(llm=MagicMock())
        agent = InvoiceAgent(MagicMock(), kit)
        assert "ocr_extract_invoice" in agent.registry.tool_names

    def test_contract_agent_registers_ocr_tools(self):
        kit = EnhancedDocumentKit(llm=MagicMock())
        agent = ContractAgent(MagicMock(), kit)
        assert "ocr_extract_contract" in agent.registry.tool_names


class TestInvoiceAgentWithOcr:
    def test_invoice_agent_react_loop_with_ocr(self):
        """InvoiceAgent should be able to use ocr_extract_invoice in its ReAct loop."""
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)

        responses = [
            # First call: decide to use OCR
            MagicMock(content='THOUGHT: User wants invoice data from a scanned PDF.\nACTION: ocr_extract_invoice\nPARAMS: {"doc_name": "invoice.pdf"}'),
            # Second call: finalize with JSON
            MagicMock(content='THOUGHT: I have the invoice JSON.\nACTION: FINAL\nRESPONSE: ```json\n{"invoice_number": "INV-2024-0056", "total": 1627.50}\n```'),
        ]
        mock_llm.invoke = MagicMock(side_effect=responses)

        # Make ocr_extract_invoice return JSON
        kit.ocr_extract_invoice = MagicMock(return_value='{"invoice_number": "INV-2024-0056", "total": 1627.50}')

        agent = InvoiceAgent(mock_llm, kit)
        result = agent.run("Extract invoice data from invoice.pdf")
        assert result.response is not None
        assert "INV-2024-0056" in result.response


class TestContractAgentWithOcr:
    def test_contract_agent_react_loop_with_ocr(self):
        """ContractAgent should be able to use ocr_extract_contract in its ReAct loop."""
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)

        responses = [
            MagicMock(content='THOUGHT: User wants contract data from a scanned PDF.\nACTION: ocr_extract_contract\nPARAMS: {"doc_name": "contract.pdf"}'),
            MagicMock(content='THOUGHT: I have the contract JSON.\nACTION: FINAL\nRESPONSE: ```json\n{"governing_law": "California", "risk_count": 1}\n```'),
        ]
        mock_llm.invoke = MagicMock(side_effect=responses)

        kit.ocr_extract_contract = MagicMock(return_value='{"governing_law": "California", "risk_count": 1}')

        agent = ContractAgent(mock_llm, kit)
        result = agent.run("Analyze contract.pdf for risks")
        assert result.response is not None
        assert "California" in result.response


class TestOcrBlockExtraction:
    def test_extract_native_page_blocks(self, tmp_path):
        """Test native PDF block extraction with titles, text, and tables."""
        import fitz
        from backend.agent.tools.ocr import extract_native_page_blocks

        pdf_path = tmp_path / "invoice_sample.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 40), "TAX INVOICE #INV-987", fontsize=18)
        page.insert_text((50, 80), "Client: Paseetah Saudi Arabia", fontsize=11)
        
        # Add table lines
        page.draw_rect(fitz.Rect(50, 110, 400, 200))
        page.draw_line(fitz.Point(50, 140), fitz.Point(400, 140))
        page.draw_line(fitz.Point(200, 110), fitz.Point(200, 200))
        page.insert_text((60, 130), "Service Item")
        page.insert_text((220, 130), "Amount")
        page.insert_text((60, 170), "Cloud AI Compute")
        page.insert_text((220, 170), "750.00")
        doc.save(str(pdf_path))
        doc.close()

        blocks = extract_native_page_blocks(pdf_path, 1)
        assert len(blocks) >= 2

        # Check title block
        title_blocks = [b for b in blocks if b["type"] == "title"]
        assert len(title_blocks) >= 1
        assert "TAX INVOICE" in title_blocks[0]["content"]
        assert "title" in title_blocks[0]
        assert "metadata" in title_blocks[0]
        assert title_blocks[0]["metadata"]["page_number"] == 1
        assert "bbox" in title_blocks[0]["metadata"]

        # Check text block
        text_blocks = [b for b in blocks if b["type"] == "text"]
        assert any("Paseetah" in b["content"] for b in text_blocks)

        # Check reading order
        orders = [b["metadata"]["reading_order"] for b in blocks]
        assert orders == sorted(orders)

    def test_ocr_extract_blocks_vision_mock(self, tmp_path):
        """Test vision OCR block extraction parsing with table:content_md and image:description."""
        pdf_path = tmp_path / "scanned.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")

        mock_renderer = MagicMock()
        mock_renderer.render_page.return_value = b"fake-png-bytes"
        mock_renderer.page_count.return_value = 1

        mock_llm = MagicMock()
        vision_json = json.dumps({
            "page_number": 1,
            "blocks": [
                {
                    "type": "title",
                    "content": "Official Report Header",
                    "title": "Official Report Header",
                    "metadata": {"bbox": [50, 20, 300, 60], "reading_order": 1}
                },
                {
                    "type": "table",
                    "content": "| Item | Price |\n|---|---|\n| API Usage | $50 |",
                    "metadata": {"bbox": [50, 100, 400, 200], "reading_order": 2},
                    "table": {
                        "content_md": "| Item | Price |\n|---|---|\n| API Usage | $50 |",
                        "headers": ["Item", "Price"],
                        "rows": [["API Usage", "$50"]]
                    }
                },
                {
                    "type": "image",
                    "content": "[Image: Corporate blue logo emblem]",
                    "metadata": {"bbox": [50, 220, 120, 280], "reading_order": 3},
                    "image": {
                        "description": "Corporate blue logo emblem with verified crest",
                        "ocr_text": "Verified"
                    }
                }
            ]
        })
        mock_llm.invoke.return_value = MagicMock(content=vision_json)

        service = OcrService(llm=mock_llm, renderer=mock_renderer)
        with patch.object(service, "_image_to_base64", return_value="b64data"):
            result = service.ocr_extract_blocks(pdf_path, page_number=1, force_ocr=True)

        assert result["total_pages"] == 1
        blocks = result["blocks"]
        assert len(blocks) == 3

        # 1. Title block
        assert blocks[0]["type"] == "title"
        assert blocks[0]["title"] == "Official Report Header"

        # 2. Table block with content_md
        assert blocks[1]["type"] == "table"
        assert "| Item | Price |" in blocks[1]["table"]["content_md"]

        # 3. Image block with description ("lil describe")
        assert blocks[2]["type"] == "image"
        assert "Corporate blue logo emblem" in blocks[2]["image"]["description"]

    def test_enhanced_kit_has_ocr_extract_blocks(self):
        kit = EnhancedDocumentKit()
        assert hasattr(kit, "ocr_extract_blocks")
        assert hasattr(kit, "ocr_page_blocks")

    def test_bilingual_language_detection(self):
        from backend.agent.tools.ocr import detect_block_language

        ar_text = "شركة الأفق للتجارة العامة - فاتورة ضريبية ورقم ضريبي"
        en_text = "Global Horizon Enterprises LLC - Commercial Invoice and VAT statement"
        mixed_text = "Tax Invoice / فاتورة ضريبية رقم INV-2026-99"

        lang_ar, dir_ar = detect_block_language(ar_text)
        assert lang_ar == "ar"
        assert dir_ar == "rtl"

        lang_en, dir_en = detect_block_language(en_text)
        assert lang_en == "en"
        assert dir_en == "ltr"

        lang_mixed, dir_mixed = detect_block_language(mixed_text)
        assert lang_mixed in ("mixed", "ar")
        assert dir_mixed == "rtl"

    def test_ocr_read_page_blocks_bilingual(self, tmp_path):
        import fitz
        from backend.agent.tools.ocr import OcrService

        pdf_path = tmp_path / "bilingual_sample.pdf"
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)

        # Add Arabic and English text
        page.insert_text((50, 100), "فاتورة مبيعات معتمدة", fontsize=16)
        page.insert_text((50, 150), "Authorized Sales Invoice from Saudi Tech Co", fontsize=11)
        doc.save(str(pdf_path))
        doc.close()

        ocr_svc = OcrService()
        res = ocr_svc.ocr_read_page_blocks(pdf_path, page_number=1, language="auto")
        assert res["page_number"] == 1
        assert "language_detected" in res
        assert "direction" in res
        assert "block_count" in res
        assert len(res["blocks"]) >= 1
