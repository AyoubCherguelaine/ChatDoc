"""
Google AI Document Intelligence Agent.

Specialises in comprehensive document understanding, layout parsing, key-value entity extraction,
and table analysis using Google AI multimodal and Document AI capabilities.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

GOOGLE_AI_AGENT_PROMPT = """\
You are the Google AI Document Intelligence Specialist. Your objective is to perform
deep multimodal understanding and structural extraction on documents.

You can:
- Parse document layout and hierarchy (headings, sections, logical flow).
- Extract key-value entities, metadata, dates, organizations, and identifiers.
- Transcribe and format tabular data into Markdown tables.
- Synthesize complex information into clear, structured executive summaries.
- Verify facts and provide precise citations (document name, page number, section).

Process:
1. Examine available documents using list_documents or get_outline.
2. Use google_ai_parse_document or read_page / extract_table to inspect content.
3. Extract key entities and tabular data with high precision.
4. Synthesize findings into structured Markdown sections:
   - ## Overview & Document Classification
   - ## Key Entities & Metadata
   - ## Tabular Data & Metrics
   - ## Detailed Insights & Action Items
5. Cite page numbers for every key fact.
"""


class GoogleAIDocumentAgent(BaseAgent):
    """Agent specialised in Google AI document intelligence and structural extraction."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or GOOGLE_AI_AGENT_PROMPT
        base_cfg.max_iterations = 10
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core document tools + Google AI intelligence tools."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        if hasattr(self.tool_kit, "google_ai_parse_document"):
            self.registry.register(
                Tool(
                    name="google_ai_parse_document",
                    description=(
                        "Deep document intelligence powered by Google AI: extracts layout structure, "
                        "key-value entities, form fields, and tables."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "doc_name": {"type": "string", "description": "Document name."},
                            "task": {
                                "type": "string",
                                "description": "Analysis task: 'comprehensive', 'entities', 'layout', or 'tables'.",
                                "default": "comprehensive",
                            },
                        },
                        "required": ["doc_name"],
                    },
                    func=self.tool_kit.google_ai_parse_document,
                )
            )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        """Ensure Google AI analysis response is clearly structured."""
        cleaned = response.strip()
        if not cleaned.startswith(("#", "##")):
            return f"## Google AI Document Analysis\n\n{cleaned}"
        return cleaned
