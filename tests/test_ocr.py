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
