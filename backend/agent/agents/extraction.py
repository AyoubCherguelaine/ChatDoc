"""
Data extraction agent.

Specialises in pulling structured data (tables, metrics, dates, names,
financial figures) from documents into clean Markdown tables.
Uses the enhanced tools (extract_table, calculate) for precision.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

EXTRACTION_AGENT_PROMPT = """\
You are a data extraction agent. Your job is to extract structured data
(metrics, dates, names, financial figures, tables) from the documents and
present them as clean Markdown tables.

Process:
1. Search for the requested data type (metrics, dates, names, etc.).
2. If a table is cited, use extract_table to get the structured data.
3. Use calculate to compute derived figures from document numbers.
4. Present results as a Markdown table with source citations for every row.
5. Preserve units and currency. Mark missing values as "Not provided".
6. Never invent or calculate figures without showing the inputs.

Extraction rules:
- Cite the source document and page/worksheet section for every row.
- If a value is an estimate or range, label it clearly.
- If numbers are in different units, normalize them in a note.
"""


class ExtractionAgent(BaseAgent):
    """Agent specialised in structured data extraction."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or EXTRACTION_AGENT_PROMPT
        base_cfg.max_iterations = 8
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core tools + enhanced extraction tools."""
        # If the tool_kit is an EnhancedDocumentKit or a DocumentToolKit with extras
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        # Add enhanced tools if available via EnhancedDocumentKit
        if hasattr(self.tool_kit, "extract_table"):
            self.registry.register(
                Tool(
                    name="extract_table",
                    description=(
                        "Extract a structured table from a specific page of a "
                        "document. Best for spreadsheets, financial tables, "
                        "and comparison grids embedded in PDFs."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "doc_name": {"type": "string", "description": "Name of the document file."},
                            "page_num": {"type": "integer", "description": "1-indexed page number."},
                            "table_index": {"type": "integer", "description": "Table index (0-based), default 0.", "default": 0},
                        },
                        "required": ["doc_name", "page_num"],
                    },
                    func=self.tool_kit.extract_table,
                )
            )
            self.registry.register(
                Tool(
                    name="calculate",
                    description=(
                        "Evaluate a mathematical expression with numbers from "
                        "the documents. Use for sums, averages, ratios, etc."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string", "description": "Math expression, e.g. '12500 + 3400'"},
                        },
                        "required": ["expression"],
                    },
                    func=self.tool_kit.calculate,
                )
            )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        # Ensure extraction results include at least a table format
        if "|" not in response and "table" not in response.lower():
            # Add a note if no table was produced
            if not response.strip():
                return "No structured data was found to extract."
        return response
