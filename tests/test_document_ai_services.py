"""
Tests for new Document AI services:
- Receipt & Expense Intelligence (ReceiptAgent)
- Talent & Resume Intelligence (ResumeAgent)
- PII & Compliance Auditor (ComplianceAgent)
- Intelligent Form Parser (FormParserAgent)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from backend.agent.agents.base import AgentResult, BaseAgent
from backend.agent.agents.compliance import ComplianceAgent
from backend.agent.agents.coordinator import CoordinatorAgent
from backend.agent.agents.form_parser import FormParserAgent
from backend.agent.agents.receipt import ReceiptAgent
from backend.agent.agents.resume import ResumeAgent
from backend.agent.tools.enhanced import EnhancedDocumentKit
from backend.documents.pdf_loader import PageText, PDFDocument

RECEIPT_SAMPLE_TEXT = """
COFFEE & BISTRO ROASTERS
456 Market St, San Francisco, CA 94105
Tel: (415) 555-9876 | Tax ID: 94-1234567

Receipt #: REC-2024-8841
Date: 2024-10-24 14:32:10
Cashier: Sarah M.

Items:
1  Espresso Single         $3.50
2  Oat Milk Flat White     $9.00
1  Avocado Toast           $12.50
1  Sparkling Water         $3.00

Subtotal:                 $28.00
Tax (8.5%):                $2.38
Tip:                       $4.00
TOTAL:                    $34.38

Payment: VISA ending in 4242
Auth Code: 091823
Category: Meals & Entertainment
"""

RESUME_SAMPLE_TEXT = """
Alex Morgan
San Francisco, CA | alex.morgan@email.com | (555) 234-5678
LinkedIn: linkedin.com/in/alexmorgan | GitHub: github.com/alexmorgan

SUMMARY
Lead Full-Stack AI Engineer with 8+ years building enterprise SaaS and generative AI systems.

SKILLS
Languages: Python, TypeScript, Go, SQL
AI/ML: PyTorch, LangChain, RAG, Vector Databases, Fine-Tuning
Frontend & Backend: React, Next.js, FastAPI, Node.js, PostgreSQL, Docker, AWS

EXPERIENCE
Staff Engineer — AI Labs (2022 - Present)
- Designed and scaled hybrid RAG system processing 10M+ queries daily.
- Managed a team of 6 engineers and reduced inference latency by 45%.

Senior Software Engineer — CloudTech Corp (2018 - 2022)
- Built automated microservices pipeline with 99.99% uptime.

EDUCATION
B.S. in Computer Science — Stanford University (2014 - 2018)
Honors: Magna Cum Laude
"""

COMPLIANCE_SAMPLE_TEXT = """
CUSTOMER ONBOARDING RECORD — CONFIDENTIAL
Internal Document Ref: SEC-2024-0019

Customer: Jane Doe
SSN: 000-12-3456
Date of Birth: 1985-04-12
Credit Card: 4111-2222-3333-4444 (CVV: 123)
Email: jane.doe@confidential-health.org
Phone: (555) 890-1234
Diagnosis Note: Patient reports chronic hypertension, prescribed Lisinopril 20mg.
Database Password: db_secret_password_2024!
"""

FORM_SAMPLE_TEXT = """
STATE HEALTH PLAN ENROLLMENT FORM
Form ID: HCF-104 | Revision: 2024-A

Section 1: Applicant Information
Full Name: Jane Doe
Date: 2024-05-10
Policy Number: POL-9928192

Section 2: Plan Selection
[X] Comprehensive Gold Coverage
[ ] Basic Silver Coverage
[ ] Catastrophic Bronze Coverage

Section 3: Authorization
Signatory: Jane Doe
Signature on file: YES
Date Signed: 2024-05-10
"""


def make_doc(name: str, text: str) -> PDFDocument:
    pages = [PageText(1, text, name, 1)]
    doc = PDFDocument(name=name, pages=pages)
    doc.full_text = text
    return doc


class TestReceiptAgent:
    def test_instantiation_and_config(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = ReceiptAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)
        assert agent.config.max_iterations == 10
        assert "extract_receipt_data" in agent.registry.tool_names
        assert "Receipt" in agent.config.system_prompt

    def test_extract_receipt_tool(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({
                "merchant": {"name": "Coffee Bistro"},
                "financials": {"total_amount": 34.38},
                "line_items": [{"description": "Espresso", "total_price": 3.50}],
            })
        )
        doc = make_doc("receipt.pdf", RECEIPT_SAMPLE_TEXT)
        kit = EnhancedDocumentKit(documents=[doc], llm=mock_llm)
        res = kit.extract_receipt_data("receipt.pdf")
        assert "Coffee Bistro" in res
        assert "34.38" in res

    def test_receipt_agent_run(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="THOUGHT: Done\nACTION: FINAL\nRESPONSE: Receipt extracted. Total: $34.38"
        )
        doc = make_doc("receipt.pdf", RECEIPT_SAMPLE_TEXT)
        kit = EnhancedDocumentKit(documents=[doc], llm=mock_llm)
        agent = ReceiptAgent(mock_llm, kit)
        result = agent.run("Extract receipt details from receipt.pdf")
        assert result.success is True
        assert "Receipt" in result.response


class TestResumeAgent:
    def test_instantiation_and_config(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = ResumeAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)
        assert agent.config.max_iterations == 10
        assert "extract_resume_data" in agent.registry.tool_names

    def test_extract_resume_tool(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({
                "candidate": {"full_name": "Alex Morgan", "email": "alex.morgan@email.com"},
                "profile_assessment": {"seniority_level": "Staff / Lead", "total_years_experience": 8},
            })
        )
        doc = make_doc("resume.pdf", RESUME_SAMPLE_TEXT)
        kit = EnhancedDocumentKit(documents=[doc], llm=mock_llm)
        res = kit.extract_resume_data("resume.pdf")
        assert "Alex Morgan" in res
        assert "Staff / Lead" in res

    def test_resume_agent_run(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="THOUGHT: Done\nACTION: FINAL\nRESPONSE: Candidate Alex Morgan evaluated."
        )
        doc = make_doc("resume.pdf", RESUME_SAMPLE_TEXT)
        kit = EnhancedDocumentKit(documents=[doc], llm=mock_llm)
        agent = ResumeAgent(mock_llm, kit)
        result = agent.run("Evaluate resume.pdf")
        assert result.success is True
        assert "Alex Morgan" in result.response


class TestComplianceAgent:
    def test_instantiation_and_config(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = ComplianceAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)
        assert agent.config.max_iterations == 10
        assert "audit_document_compliance" in agent.registry.tool_names

    def test_audit_compliance_tool(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({
                "compliance_status": "Critical Risk",
                "risk_score": 95,
                "pii_detected": [{"type": "SSN", "snippet": "000-12-3456"}],
            })
        )
        doc = make_doc("record.pdf", COMPLIANCE_SAMPLE_TEXT)
        kit = EnhancedDocumentKit(documents=[doc], llm=mock_llm)
        res = kit.audit_document_compliance("record.pdf")
        assert "Critical Risk" in res
        assert "000-12-3456" in res

    def test_compliance_agent_run(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="THOUGHT: Done\nACTION: FINAL\nRESPONSE: High risk PII detected: SSN and Credit Card."
        )
        doc = make_doc("record.pdf", COMPLIANCE_SAMPLE_TEXT)
        kit = EnhancedDocumentKit(documents=[doc], llm=mock_llm)
        agent = ComplianceAgent(mock_llm, kit)
        result = agent.run("Audit record.pdf for GDPR compliance")
        assert result.success is True
        assert "PII" in result.response


class TestFormParserAgent:
    def test_instantiation_and_config(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = FormParserAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)
        assert agent.config.max_iterations == 10
        assert "extract_form_fields" in agent.registry.tool_names

    def test_extract_form_fields_tool(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content=json.dumps({
                "form_metadata": {"form_title": "Health Plan Enrollment", "form_id": "HCF-104"},
                "checkboxes_and_radios": [{"label": "Gold Coverage", "is_selected": True}],
            })
        )
        doc = make_doc("form.pdf", FORM_SAMPLE_TEXT)
        kit = EnhancedDocumentKit(documents=[doc], llm=mock_llm)
        res = kit.extract_form_fields("form.pdf")
        assert "HCF-104" in res
        assert "Gold Coverage" in res

    def test_form_parser_agent_run(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="THOUGHT: Done\nACTION: FINAL\nRESPONSE: Form HCF-104 parsed successfully."
        )
        doc = make_doc("form.pdf", FORM_SAMPLE_TEXT)
        kit = EnhancedDocumentKit(documents=[doc], llm=mock_llm)
        agent = FormParserAgent(mock_llm, kit)
        result = agent.run("Parse form.pdf")
        assert result.success is True
        assert "HCF-104" in result.response


class TestRAGFactoryAndCoordinator:
    def test_rag_build_all_new_agents(self):
        class MockBundle:
            def __init__(self):
                self.vector_store = MagicMock()
                self.vector_store.search = lambda *a, **kw: []
                self.pdf_docs = [make_doc("test.pdf", "Sample text")]
                self.chunks = []

        bundle = MockBundle()
        with patch("backend.rag.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            from backend.rag import _build_agent

            modes_to_test = [
                ("receipt", ReceiptAgent, "extract_receipt_data"),
                ("resume", ResumeAgent, "extract_resume_data"),
                ("compliance", ComplianceAgent, "audit_document_compliance"),
                ("form_parser", FormParserAgent, "extract_form_fields"),
            ]

            for mode_name, expected_cls, expected_tool in modes_to_test:
                agent = _build_agent(bundle, "gpt-4o-mini", mode=mode_name)
                assert isinstance(agent, expected_cls)
                assert expected_tool in agent.registry.tool_names

    def test_coordinator_delegates_to_new_services(self):
        mock_llm = MagicMock()
        responses = [
            'THOUGHT: Delegate to receipt agent\nACTION: delegate\nPARAMS: {"agent": "receipt", "query": "Process receipt.pdf"}',
            'THOUGHT: Have the receipt info\nACTION: FINAL\nRESPONSE: Total was $34.38 at Coffee Bistro.',
        ]
        iter_resp = iter(responses)
        mock_llm.invoke = lambda prompt: MagicMock(content=next(iter_resp))

        kit = EnhancedDocumentKit(llm=mock_llm)
        coordinator = CoordinatorAgent(mock_llm, kit)

        sub_receipt = MagicMock()
        sub_receipt.run.return_value = AgentResult(
            response="Coffee Bistro: $34.38 total", steps=[], success=True, iterations=1
        )
        coordinator.register_sub_agent("receipt", sub_receipt)

        result = coordinator.run("Process receipt.pdf")
        assert result.success is True
        assert "34.38" in result.response

    def test_invoice_and_prose_structured_extraction(self):
        from backend.v1.routes import extract_structured_data, _extract_json_from_text
        from backend.server import _format_service_result

        # Test 1: Markdown prose with bullet points
        prose = """
Here are the extracted invoice details:
- Vendor Name: Gulf Consulting Services
- Tax ID: 310293847500003
- Invoice Number: INV-88219
- Invoice Date: 2026-10-15
- Total Amount: 4,500.00 SAR
- VAT 15%: 675.00 SAR
- Grand Total: 5,175.00 SAR
        """
        extracted = extract_structured_data(prose, service="invoice")
        assert isinstance(extracted, dict)
        assert extracted.get("vendor_name") == "Gulf Consulting Services"
        assert extracted.get("invoice_number") == "INV-88219"
        assert extracted.get("grand_total") == "5,175.00 SAR"

        # Test 2: Fenced code block with commentary
        fenced = """
Analysis complete:
```json
{
  "vendor": "Acme Tools Ltd",
  "invoice_number": "INV-001",
  "total": 1250.00,
  "line_items": [
    {"description": "Cloud hosting", "amount": 1250.00}
  ]
}
```
Thank you.
        """
        parsed_fenced = _extract_json_from_text(fenced)
        assert isinstance(parsed_fenced, dict)
        assert parsed_fenced["vendor"] == "Acme Tools Ltd"
        assert parsed_fenced["total"] == 1250.00

        # Test 3: _format_service_result guarantees data and result
        doc = {"id": "doc-test-1", "original_filename": "invoice_sample.pdf"}
        agent_res = AgentResult(response=prose, steps=[], success=True, iterations=2)
        bundle_mock = MagicMock()
        formatted = _format_service_result(doc, "invoice", agent_res, bundle_mock, cost=10, remaining=990)
        assert formatted["success"] is True
        assert formatted["data"] is not None
        assert isinstance(formatted["data"], dict)
        assert "grand_total" in formatted["data"]
        # result must be pretty-printed JSON
        parsed_from_result = json.loads(formatted["result"])
        assert parsed_from_result["invoice_number"] == "INV-88219"
