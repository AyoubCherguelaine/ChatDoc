"""
Document comparison agent.

Specialises in comparing information across multiple documents — finding
how each document treats the same subject, highlighting agreements and
discrepancies.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

COMPARISON_AGENT_PROMPT = """\
You are a document comparison specialist. Your job is to compare information across
documents (or across sections/clauses within a document) and highlight how each source
treats the subject.

Process:
1. List all available documents first using list_documents.
2. Use compare_documents or search_documents to gather evidence on the topic.
3. Read specific pages using read_page or read_pages where different documents give conflicting or
   complementary information.
4. If only one document is available, compare different sections, clauses, or historical/revised terms
   within that document, noting that uploading more documents enables cross-file comparison.
5. Produce a structured comparison:
   - ## Document Comparison
   - ### Key Agreements & Shared Provisions
   - ### Discrepancies, Contradictions & Divergences
   - ### Unique Contributions by Source
6. Cite document name and page number for every factual claim.

Focus on:
- Where documents agree or disagree
- What each document uniquely contributes
- Contradictions, discrepancies, or knowledge gaps
"""


class ComparisonAgent(BaseAgent):
    """Agent specialised in multi-document comparison and discrepancy analysis."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or COMPARISON_AGENT_PROMPT
        base_cfg.max_iterations = 8
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register tools with fallback to ensure compare_documents is always available."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        # Fallback registration if compare_documents was omitted
        if "compare_documents" not in self.registry.tool_names:
            if hasattr(self.tool_kit, "compare_documents"):
                self.registry.register(
                    Tool(
                        name="compare_documents",
                        description="Compare information across documents or sections.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Topic or query to compare."},
                                "top_k_per_doc": {"type": "integer", "description": "Results per document.", "default": 3},
                            },
                            "required": ["query"],
                        },
                        func=self.tool_kit.compare_documents,
                    )
                )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        # Ensure comparison structure
        clean_resp = response.strip()
        if "## " not in clean_resp and "Comparison" not in clean_resp:
            clean_resp = "## Comparison\n\n" + clean_resp
        return clean_resp
