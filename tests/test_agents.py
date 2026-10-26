"""Tests for the multi-agent framework and enhanced document tools."""

from unittest.mock import MagicMock

from langchain_core.documents import Document

from backend.agent.agents.base import AgentResult, BaseAgent, BaseAgentConfig
from backend.agent.agents.comparison import ComparisonAgent
from backend.agent.agents.contract import ContractAgent
from backend.agent.agents.coordinator import CoordinatorAgent
from backend.agent.agents.extraction import ExtractionAgent
from backend.agent.agents.factcheck import FactCheckAgent
from backend.agent.agents.google_ai import GoogleAIDocumentAgent
from backend.agent.agents.invoice import InvoiceAgent
from backend.agent.agents.research import ResearchAgent
from backend.agent.agents.summary import SummaryAgent
from backend.agent.tools.document_tools import DocumentToolKit
from backend.agent.tools.enhanced import EnhancedDocumentKit
from backend.documents.pdf_loader import PageText, PDFDocument

# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------


class TestBaseAgent:
    def test_inherits_from_base_agent(self):
        from backend.agent.agent import FreeAgent

        assert issubclass(FreeAgent, BaseAgent)

    def test_init_sets_registry(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = BaseAgent(mock_llm, kit)
        assert agent.registry is not None
        assert agent.config is not None

    def test_post_process_default_is_passthrough(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = BaseAgent(mock_llm, kit)
        assert agent._post_process("Hello", []) == "Hello"


# ---------------------------------------------------------------------------
# Specialized agents
# ---------------------------------------------------------------------------


class TestSummaryAgent:
    def test_config_defaults(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = SummaryAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)
        assert agent.config.max_iterations == 8
        assert agent.config.system_prompt != ""

    def test_post_process_adds_header(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = SummaryAgent(mock_llm, kit)
        result = agent._post_process("Plain text summary", [])
        assert result.startswith("## Executive Summary")

    def test_post_process_preserves_markdown(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = SummaryAgent(mock_llm, kit)
        result = agent._post_process("## Already structured", [])
        assert result.startswith("## Already structured")


class TestResearchAgent:
    def test_is_base_agent(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = ResearchAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)

    def test_config_max_iterations(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = ResearchAgent(mock_llm, kit)
        assert agent.config.max_iterations == 10


class TestExtractionAgent:
    def test_registers_enhanced_tools(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = ExtractionAgent(mock_llm, kit)
        names = set(agent.registry.tool_names)
        assert "extract_table" in names
        assert "calculate" in names

    def test_does_not_register_enhanced_if_unavailable(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = ExtractionAgent(mock_llm, kit)
        assert "extract_table" not in agent.registry.tool_names


class TestComparisonAgent:
    def test_prompt_contains_comparison_guidance(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = ComparisonAgent(mock_llm, kit)
        assert "comparison" in agent.config.system_prompt.lower()

    def test_post_process_adds_header(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = ComparisonAgent(mock_llm, kit)
        result = agent._post_process("Some comparison text", [])
        assert "## Comparison" in result


class TestFactCheckAgent:
    def test_registers_verify_fact(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = FactCheckAgent(mock_llm, kit)
        assert "verify_fact" in agent.registry.tool_names

    def test_does_not_register_verify_fact_unavailable(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        agent = FactCheckAgent(mock_llm, kit)
        assert "verify_fact" not in agent.registry.tool_names


# ---------------------------------------------------------------------------
# InvoiceAgent
# ---------------------------------------------------------------------------


class TestInvoiceAgent:
    def test_is_base_agent(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = InvoiceAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)

    def test_config_max_iterations(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = InvoiceAgent(mock_llm, kit)
        assert agent.config.max_iterations == 10

    def test_registers_invoice_tools(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = InvoiceAgent(mock_llm, kit)
        assert "extract_invoice_data" in agent.registry.tool_names
        assert "calculate" in agent.registry.tool_names


# ---------------------------------------------------------------------------
# ContractAgent
# ---------------------------------------------------------------------------


class TestContractAgent:
    def test_is_base_agent(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = ContractAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)

    def test_config_max_iterations(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = ContractAgent(mock_llm, kit)
        assert agent.config.max_iterations == 12

    def test_registers_contract_tools(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = ContractAgent(mock_llm, kit)
        assert "extract_contract_data" in agent.registry.tool_names
        assert "calculate" in agent.registry.tool_names


# ---------------------------------------------------------------------------
# GoogleAIDocumentAgent
# ---------------------------------------------------------------------------


class TestGoogleAIDocumentAgent:
    def test_is_base_agent(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = GoogleAIDocumentAgent(mock_llm, kit)
        assert isinstance(agent, BaseAgent)

    def test_config_defaults(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = GoogleAIDocumentAgent(mock_llm, kit)
        assert agent.config.max_iterations == 10
        assert "Google AI" in agent.config.system_prompt

    def test_registers_google_ai_tools(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = GoogleAIDocumentAgent(mock_llm, kit)
        assert "google_ai_parse_document" in agent.registry.tool_names

    def test_post_process_adds_header(self):
        mock_llm = MagicMock()
        kit = EnhancedDocumentKit(llm=mock_llm)
        agent = GoogleAIDocumentAgent(mock_llm, kit)
        res = agent._post_process("Extracted content without markdown header", [])
        assert res.startswith("## Google AI Document Analysis")


# ---------------------------------------------------------------------------
# CoordinatorAgent
# ---------------------------------------------------------------------------


class TestCoordinatorAgent:
    def test_init(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        coordinator = CoordinatorAgent(mock_llm, kit)
        assert isinstance(coordinator, BaseAgent)
        assert "delegate" in coordinator.registry.tool_names

    def test_register_sub_agent(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        coordinator = CoordinatorAgent(mock_llm, kit)
        sub = SummaryAgent(mock_llm, kit)
        coordinator.register_sub_agent("summary", sub)
        assert "summary" in coordinator.sub_agent_names

    def test_register_sub_agent_factory(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        coordinator = CoordinatorAgent(mock_llm, kit)
        coordinator.register_sub_agent_factory("summary", lambda: SummaryAgent(mock_llm, kit))
        assert "summary" in coordinator.sub_agent_names

    def test_delegate_runs_sub_agent(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        coordinator = CoordinatorAgent(mock_llm, kit)

        sub = MagicMock()
        sub.run.return_value = AgentResult(response="Sub answer", steps=[], success=True, iterations=1)
        coordinator.register_sub_agent("summary", sub)

        result = coordinator._delegate("summary", "Summarize this")
        assert result == "Sub answer"
        sub.run.assert_called_once_with("Summarize this")

    def test_delegate_unknown_agent(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        coordinator = CoordinatorAgent(mock_llm, kit)
        result = coordinator._delegate("nonexistent", "test")
        assert "ERROR" in result
        assert "Unknown agent" in result

    def test_delegate_failure_returns_error(self):
        mock_llm = MagicMock()
        kit = DocumentToolKit()
        coordinator = CoordinatorAgent(mock_llm, kit)

        sub = MagicMock()
        sub.run.side_effect = RuntimeError("boom")
        coordinator.register_sub_agent("research", sub)

        result = coordinator._delegate("research", "test query")
        assert "ERROR" in result
        assert "boom" in result


# ---------------------------------------------------------------------------
# EnhancedDocumentKit tools
# ---------------------------------------------------------------------------


class TestEnhancedDocumentKit:
    def test_init(self):
        kit = EnhancedDocumentKit()
        assert kit.vector_store is None
        assert kit.documents == []
        assert kit.llm is None

    def test_init_with_data(self):
        mock_vs = MagicMock()
        docs = [PDFDocument(name="test.pdf", pages=[PageText(1, "text", "test.pdf", 1)])]
        kit = EnhancedDocumentKit(vector_store=mock_vs, documents=docs)
        assert kit._doc_map["test.pdf"] is not None

    def test_from_kit(self):
        kit = DocumentToolKit()
        enhanced = EnhancedDocumentKit.from_kit(kit)
        assert enhanced.documents == kit.documents
        assert enhanced.vector_store == kit.vector_store

    def test_add_documents(self):
        kit = EnhancedDocumentKit()
        docs = [PDFDocument(name="d1.pdf", pages=[PageText(1, "t", "d1.pdf", 1)])]
        kit.add_documents(docs)
        assert kit._doc_map["d1.pdf"] is not None

    def test_calculate_basic(self):
        kit = EnhancedDocumentKit()
        result = kit.calculate("2 + 3 * 4")
        assert "14" in result

    def test_calculate_complex(self):
        kit = EnhancedDocumentKit()
        result = kit.calculate("100 / (10 + 15)")
        assert "4" in result

    def test_calculate_invalid(self):
        kit = EnhancedDocumentKit()
        result = kit.calculate("__import__('os')")
        assert "ERROR" in result

    def test_calculate_empty(self):
        kit = EnhancedDocumentKit()
        result = kit.calculate("")
        assert "ERROR" in result

    def test_extract_table_no_file(self):
        kit = DocumentToolKit()
        enhanced = EnhancedDocumentKit.from_kit(kit)
        enhanced.documents = [
            PDFDocument(name="test.pdf", pages=[PageText(1, "text", "test.pdf", 1)])
        ]
        result = enhanced.extract_table("test.pdf", 1)
        assert "ERROR" in result or "table" in result.lower() or "No tables" in result

    def test_extract_invoice_data_no_doc(self):
        kit = EnhancedDocumentKit(llm=MagicMock())
        result = kit.extract_invoice_data("nonexistent.pdf")
        assert "ERROR" in result

    def test_extract_invoice_data_no_llm(self):
        kit = EnhancedDocumentKit()
        kit.documents = [
            PDFDocument(name="test.pdf", pages=[PageText(1, "text", "test.pdf", 1)])
        ]
        result = kit.extract_invoice_data("test.pdf")
        assert "ERROR" in result

    def test_extract_contract_data_no_doc(self):
        kit = EnhancedDocumentKit(llm=MagicMock())
        result = kit.extract_contract_data("nonexistent.pdf")
        assert "ERROR" in result

    def test_extract_contract_data_no_llm(self):
        kit = EnhancedDocumentKit()
        kit.documents = [
            PDFDocument(name="test.pdf", pages=[PageText(1, "text", "test.pdf", 1)])
        ]
        result = kit.extract_contract_data("test.pdf")
        assert "ERROR" in result

    def test_verify_fact_no_store(self):
        kit = EnhancedDocumentKit()
        result = kit.verify_fact("some claim")
        assert "ERROR" in result

    def test_verify_fact_with_store(self):
        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            Document(page_content="evidence text", metadata={"doc_name": "doc.pdf", "start_page": 1}),
        ]
        kit = EnhancedDocumentKit(vector_store=mock_vs, llm=MagicMock())
        result = kit.verify_fact("claim to verify")
        assert "Fact-check" in result or "Evidence" in result
        mock_vs.search.assert_called_once()

    def test_get_outline_not_found(self):
        kit = EnhancedDocumentKit()
        result = kit.get_outline("nonexistent.pdf")
        assert "ERROR" in result or "not found" in result.lower()

    def test_google_ai_parse_document_no_doc(self):
        kit = EnhancedDocumentKit()
        result = kit.google_ai_parse_document("nonexistent.pdf")
        assert "ERROR" in result

    def test_google_ai_parse_document_with_doc(self):
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "## Google AI Document Intelligence\nSummary and Entities"
        mock_llm.invoke.return_value = mock_resp

        kit = EnhancedDocumentKit(llm=mock_llm)
        kit.documents = [
            PDFDocument(name="sample.pdf", pages=[PageText(1, "Sample contract content", "sample.pdf", 1)])
        ]
        result = kit.google_ai_parse_document("sample.pdf")
        assert "Google AI" in result or "Summary" in result


# ---------------------------------------------------------------------------
# Agent mode integration
# ---------------------------------------------------------------------------


class TestAgentModes:
    def test_all_specialized_agents_usable(self):
        """Each specialized agent should be instantiable and runnable."""

        mock_llm = MagicMock()

        def make_response(text):
            mock_msg = MagicMock()
            mock_msg.content = text
            return mock_msg

        mock_llm.invoke = lambda prompt: make_response(
            "THOUGHT: Done\nACTION: FINAL\nRESPONSE: Summary complete"
        )

        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            Document(page_content="content", metadata={"doc_name": "d.pdf", "start_page": 1})
        ]
        kit = EnhancedDocumentKit(vector_store=mock_vs, documents=[], llm=mock_llm)

        for agent_cls in [SummaryAgent, ResearchAgent, ExtractionAgent,
                          ComparisonAgent, FactCheckAgent, InvoiceAgent,
                          ContractAgent, GoogleAIDocumentAgent]:
            agent = agent_cls(mock_llm, kit)
            result = agent.run("Test query")
            assert result.response is not None
            assert isinstance(result, AgentResult)

    def test_coordinator_delegates_then_synthesizes(self):
        """Coordinator should delegate to a sub-agent and reach a final answer."""
        mock_llm = MagicMock()

        responses = [
            # Coordinator decides to delegate
            'THOUGHT: This is a summarization request\nACTION: delegate\nPARAMS: {"agent": "summary", "query": "Summarize this document"}',
            # Coordinator sees the result and gives final answer
            'THOUGHT: I have the summary. Now I can answer.\nACTION: FINAL\nRESPONSE: The document summary is ready.',
        ]
        iter_responses = iter(responses)
        mock_llm.invoke = lambda prompt: MagicMock(content=next(iter_responses))

        kit = DocumentToolKit()

        coordinator = CoordinatorAgent(
            mock_llm, kit, config=BaseAgentConfig(max_iterations=5, verbose=False)
        )

        sub = MagicMock()
        sub.run.return_value = AgentResult(
            response="Document summary here...", steps=[], success=True, iterations=1
        )
        coordinator.register_sub_agent("summary", sub)

        result = coordinator.run("Summarize this document")
        assert result.success is True
        assert "Document summary" in result.response or "summary is ready" in result.response
