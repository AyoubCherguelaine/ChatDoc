"""Tests for agent/agent.py, agent/tools/, and agent/prompts.py"""

import json
from unittest.mock import AsyncMock, MagicMock

from langchain_core.documents import Document

from backend.agent.prompts import (
    format_scratchpad,
    parse_agent_output,
)
from backend.agent.tools.document_tools import DocumentToolKit
from backend.agent.tools.registry import Tool, ToolRegistry

# ---------------------------------------------------------------------------
# Tool dataclass
# ---------------------------------------------------------------------------


class TestTool:
    def test_creation(self):
        def my_func(query: str) -> str:
            """Does something."""
            return f"result for {query}"

        tool = Tool(
            name="my_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            func=my_func,
        )
        assert tool.name == "my_tool"
        assert tool.description == "A test tool"

    def test_call(self):
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        tool = Tool.from_function(add)
        result = tool.func(a=2, b=3)
        assert result == 5

    def test_call_error(self):
        def fail():
            """Fails."""
            raise ValueError("boom")

        tool = Tool(name="fail", description="fails", parameters={}, func=fail)
        result = str(tool())
        assert "ERROR" in result

    def test_from_function_auto_schema(self):
        def my_func(query: str, top_k: int = 5) -> str:
            """Searches things."""
            return query

        tool = Tool.from_function(my_func)
        assert tool.name == "my_func"
        assert "query" in tool.parameters["properties"]
        assert "query" in tool.parameters["required"]
        assert tool.parameters["properties"]["top_k"]["type"] == "integer"

    def test_schema_json(self):
        tool = Tool(
            name="t",
            description="d",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            func=lambda x: x,
        )
        schema = json.loads(tool.schema_json)
        assert schema["type"] == "object"

    def test_acall(self):
        async_func = AsyncMock(return_value="async result")
        tool = Tool(name="async_tool", description="d", parameters={}, func=lambda: "sync", async_func=async_func)
        import asyncio

        result = asyncio.new_event_loop().run_until_complete(tool.acall())
        assert result == "async result"


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_register_and_get(self):
        tool = Tool(name="search", description="d", parameters={}, func=lambda: "ok")
        registry = ToolRegistry([tool])
        assert registry.get("search") is tool
        assert "search" in registry.tool_names

    def test_register_all_returns_self(self):
        registry = ToolRegistry()
        tool = Tool(name="t", description="d", parameters={}, func=lambda: "ok")
        result = registry.register(tool)
        assert result is registry

    def test_unregister(self):
        tool = Tool(name="t", description="d", parameters={}, func=lambda: "ok")
        registry = ToolRegistry([tool])
        registry.unregister("t")
        assert registry.get("t") is None

    def test_execute(self):
        def add(a: int, b: int) -> int:
            return a + b

        tool = Tool(name="add", description="d", parameters={}, func=add)
        registry = ToolRegistry([tool])
        result = registry.execute("add", {"a": 2, "b": 3})
        assert "5" in result

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("unknown", {})
        assert "Unknown tool" in result

    def test_aexecute(self):
        import asyncio

        async_func = AsyncMock(return_value="async ok")
        tool = Tool(name="async_tool", description="d", parameters={}, func=lambda: "sync", async_func=async_func)
        registry = ToolRegistry([tool])
        result = asyncio.new_event_loop().run_until_complete(registry.aexecute("async_tool", {}))
        assert result == "async ok"

    def test_len(self):
        tools = [
            Tool(name="t1", description="d", parameters={}, func=lambda: 1),
            Tool(name="t2", description="d", parameters={}, func=lambda: 2),
        ]
        registry = ToolRegistry(tools)
        assert len(registry) == 2

    def test_format_tool_descriptions(self):
        tool = Tool(
            name="search",
            description="Search docs",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
            func=lambda q: q,
        )
        registry = ToolRegistry([tool])
        desc = registry.format_tool_descriptions()
        assert "search" in desc
        assert "Search docs" in desc


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


class TestParseAgentOutput:
    def test_final_response(self):
        text = """THOUGHT: I have enough info.
ACTION: FINAL
RESPONSE: The answer is 42."""
        result = parse_agent_output(text)
        assert result["action"] == "FINAL"
        assert result["response"] == "The answer is 42."
        assert "enough info" in result["thought"]

    def test_tool_action(self):
        text = """THOUGHT: Let me search.
ACTION: search_documents
PARAMS: {"query": "test", "top_k": 3}"""
        result = parse_agent_output(text)
        assert result["action"] == "search_documents"
        assert result["params"]["query"] == "test"
        assert result["params"]["top_k"] == 3

    def test_missing_final_response(self):
        text = """THOUGHT: Not sure.
ACTION: FINAL"""
        result = parse_agent_output(text)
        assert result["action"] == "FINAL"
        assert result["response"] == ""

    def test_missing_thought(self):
        text = """ACTION: FINAL
RESPONSE: Hi"""
        result = parse_agent_output(text)
        assert result["thought"] == ""

    def test_action_with_trailing_punctuation(self):
        text = """THOUGHT: searching
ACTION: search_documents.
PARAMS: {"query": "q"}"""
        result = parse_agent_output(text)
        # The dot should be stripped
        assert result["action"] == "search_documents"

    def test_invalid_json_params(self):
        text = """THOUGHT: searching
ACTION: search
PARAMS: not json"""
        result = parse_agent_output(text)
        assert result["params"] == {}

    def test_no_action_defaults_to_final(self):
        text = "Just some text without markers"
        result = parse_agent_output(text)
        assert result["action"] == "FINAL"


class TestFormatScratchpad:
    def test_empty_steps(self):
        result = format_scratchpad([])
        assert "no previous steps" in result

    def test_with_steps(self):
        steps = [
            {
                "thought": "search",
                "action": "search_documents",
                "params": {"query": "test"},
                "observation": "Found something here that is very long " * 100,
            }
        ]
        result = format_scratchpad(steps)
        assert "Step 1" in result
        assert "search_documents" in result
        assert "[truncated]" in result  # observation longer than 500 chars


# ---------------------------------------------------------------------------
# DocumentToolKit
# ---------------------------------------------------------------------------


class TestDocumentToolKit:
    def test_init(self):
        kit = DocumentToolKit()
        assert kit.vector_store is None
        assert kit.documents == []
        assert kit._doc_map == {}

    def test_init_with_data(self):
        from backend.documents.pdf_loader import PageText, PDFDocument

        vs = MagicMock()
        docs = [PDFDocument(name="test.pdf", pages=[PageText(1, "text", "test.pdf", 1)])]
        kit = DocumentToolKit(vector_store=vs, documents=docs)
        assert kit._doc_map["test.pdf"] is not None

    def test_find_document_exact(self):
        from backend.documents.pdf_loader import PageText, PDFDocument

        docs = [PDFDocument(name="report.pdf", pages=[PageText(1, "t", "report.pdf", 1)])]
        kit = DocumentToolKit(documents=docs)
        assert kit._find_document("report.pdf") is not None

    def test_find_document_fuzzy(self):
        from backend.documents.pdf_loader import PageText, PDFDocument

        docs = [PDFDocument(name="Annual_Report.pdf", pages=[PageText(1, "t", "AR", 1)])]
        kit = DocumentToolKit(documents=docs)
        assert kit._find_document("annual") is not None

    def test_find_document_not_found(self):
        kit = DocumentToolKit()
        assert kit._find_document("nonexistent.pdf") is None

    def test_search_documents_no_store(self):
        kit = DocumentToolKit()
        result = kit.search_documents("query")
        assert "ERROR" in result

    def test_search_documents_with_store(self):
        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            Document(page_content="content here", metadata={"doc_name": "doc.pdf", "start_page": 1, "end_page": 2}),
        ]
        kit = DocumentToolKit(vector_store=mock_vs)
        result = kit.search_documents("test query", top_k=3)
        assert "Result 1" in result
        assert "doc.pdf" in result
        mock_vs.search.assert_called_once_with("test query", top_k=3)

    def test_read_page_not_found(self):
        kit = DocumentToolKit()
        result = kit.read_page("nonexistent.pdf", 1)
        assert "ERROR" in result
        assert "Available" in result

    def test_read_page_out_of_range(self):
        from backend.documents.pdf_loader import PageText, PDFDocument

        docs = [PDFDocument(name="test.pdf", pages=[PageText(1, "text", "test.pdf", 3)])]
        kit = DocumentToolKit(documents=docs)
        result = kit.read_page("test.pdf", 5)
        assert "out of range" in result

    def test_read_pages_swap_range(self):
        from backend.documents.pdf_loader import PageText, PDFDocument

        docs = [
            PDFDocument(
                name="test.pdf",
                pages=[
                    PageText(1, "P1", "test.pdf", 3),
                    PageText(2, "P2", "test.pdf", 3),
                    PageText(3, "P3", "test.pdf", 3),
                ],
            )
        ]
        kit = DocumentToolKit(documents=docs)
        result = kit.read_pages("test.pdf", 3, 1)
        assert "P1" in result
        assert "P3" in result

    def test_list_documents_empty(self):
        kit = DocumentToolKit()
        result = kit.list_documents()
        assert "No documents" in result

    def test_list_documents_with_docs(self):
        from backend.documents.pdf_loader import PageText, PDFDocument

        docs = [
            PDFDocument(
                name="test.pdf",
                pages=[
                    PageText(1, "t", "test.pdf", 2),
                    PageText(2, "t2", "test.pdf", 2),
                ],
                file_path="/path/test.pdf",
            )
        ]
        kit = DocumentToolKit(documents=docs)
        result = kit.list_documents()
        assert "test.pdf" in result
        assert "2 pages" in result

    def test_summarize_no_text(self):
        kit = DocumentToolKit()
        result = kit.summarize("")
        assert "No text" in result

    def test_summarize_extractive(self):
        kit = DocumentToolKit()
        text = "First sentence. Second sentence. Third sentence."
        result = kit.summarize(text)
        assert "First sentence" in result

    def test_compare_documents_empty(self):
        kit = DocumentToolKit()
        result = kit.compare_documents("topic")
        assert "No documents" in result

    def test_register_all(self):
        kit = DocumentToolKit()
        registry = ToolRegistry()
        kit.register_all(registry)
        expected = {
            "search_documents",
            "read_page",
            "read_pages",
            "list_documents",
            "summarize",
            "compare_documents",
            "get_metadata",
        }
        assert expected.issubset(set(registry.tool_names))


# ---------------------------------------------------------------------------
# FreeAgent
# ---------------------------------------------------------------------------


class TestFreeAgent:
    def _make_mock_llm(self, responses: list[str]):
        """Create a mock LLM that returns preset responses."""
        mock_llm = MagicMock()

        response_iter = iter(responses)

        def invoke(prompt):
            resp_text = next(response_iter)
            mock_msg = MagicMock()
            mock_msg.content = resp_text
            return mock_msg

        mock_llm.invoke = invoke
        return mock_llm

    def _make_kit(self):
        mock_vs = MagicMock()
        mock_vs.search.return_value = [
            Document(
                page_content="relevant content", metadata={"doc_name": "test.pdf", "start_page": 1, "end_page": 1}
            ),
        ]
        kit = DocumentToolKit(vector_store=mock_vs)
        return kit

    def test_init(self):
        from backend.agent.agent import FreeAgent

        mock_llm = self._make_mock_llm(["THOUGHT: done\nACTION: FINAL\nRESPONSE: Answer"])
        kit = self._make_kit()
        agent = FreeAgent(llm=mock_llm, tool_kit=kit)
        assert agent.llm is mock_llm
        assert agent.registry is not None
        assert len(agent.registry.tools) > 0

    def test_run_final_answer(self):
        from backend.agent.agent import AgentConfig, FreeAgent

        mock_llm = self._make_mock_llm(
            [
                "THOUGHT: I can answer directly.\nACTION: FINAL\nRESPONSE: The answer is 42.",
            ]
        )
        kit = self._make_kit()
        agent = FreeAgent(
            llm=mock_llm,
            tool_kit=kit,
            config=AgentConfig(max_iterations=5, verbose=False),
        )
        result = agent.run("What is everything?")
        assert result.success is True
        assert result.response == "The answer is 42."
        assert result.iterations == 1

    def test_run_tool_then_final(self):
        from backend.agent.agent import AgentConfig, FreeAgent

        mock_llm = self._make_mock_llm(
            [
                'THOUGHT: I should search.\nACTION: search_documents\nPARAMS: {"query": "test"}',
                "THOUGHT: I found the answer.\nACTION: FINAL\nRESPONSE: Found it on page 1.",
            ]
        )
        kit = self._make_kit()
        agent = FreeAgent(
            llm=mock_llm,
            tool_kit=kit,
            config=AgentConfig(max_iterations=5, verbose=False),
        )
        result = agent.run("What did I ask?")
        assert result.success is True
        assert result.response == "Found it on page 1."
        assert result.iterations == 2
        assert len(result.steps) == 2
        # First step should have a search action
        assert result.steps[0]["action"] == "search_documents"
        assert result.steps[1]["action"] == "FINAL"

    def test_run_max_iterations(self):
        from backend.agent.agent import AgentConfig, FreeAgent

        # Agent always tries to search, never gives final answer
        mock_llm = self._make_mock_llm(['THOUGHT: search again\nACTION: search_documents\nPARAMS: {"query": "q"}'] * 10)
        kit = self._make_kit()
        agent = FreeAgent(
            llm=mock_llm,
            tool_kit=kit,
            config=AgentConfig(max_iterations=3, verbose=False),
        )
        result = agent.run("What?")
        assert result.success is False
        assert result.iterations == 3

    def test_run_unknown_tool_continues(self):
        from backend.agent.agent import AgentConfig, FreeAgent

        mock_llm = self._make_mock_llm(
            [
                "THOUGHT: use unknown tool\nACTION: nonexistent_tool\nPARAMS: {}",
                "THOUGHT: now final\nACTION: FINAL\nRESPONSE: Done.",
            ]
        )
        kit = self._make_kit()
        agent = FreeAgent(
            llm=mock_llm,
            tool_kit=kit,
            config=AgentConfig(max_iterations=5, verbose=False, stop_after_no_action=False),
        )
        result = agent.run("test")
        assert result.success is True

    def test_agent_result_dataclass(self):
        from backend.agent.agent import AgentResult

        result = AgentResult(response="test", steps=[], success=True, iterations=1)
        assert result.response == "test"
        assert result.success is True
