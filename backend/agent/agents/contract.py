"""
Contract analysis agent.

Specialises in extracting structured contract data and identifying key
clauses, obligations, risks, renewal terms, and termination conditions.

Uses :class:`EnhancedDocumentKit` (or compatible kit) for contract-specific
tools.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

CONTRACT_AGENT_PROMPT = """\
You are a contract analysis agent. Your job is to extract structured data
from contracts and legal documents, identify key clauses, obligations,
risks, and present findings as clean JSON.

You can identify and extract:
- Parties (names, addresses, roles)
- Effective date and expiration / renewal dates
- Governing law and jurisdiction
- Key clauses (termination, indemnification, confidentiality, force majeure,
  dispute resolution, scope of work)
- Payment terms and obligations
- Renewal and auto-renewal clauses
- Risk flags (one-sided clauses, missing definitions, undefined terms)

Process:
1. Search the document for contract-related content.
2. Use extract_contract_data to pull structured fields.
3. Flag potential risks or unusual clauses.
4. Present results as a JSON object with source citations.
5. If the document is not a contract, report that and switch to general
   document Q&A using your search tools.
"""


class ContractAgent(BaseAgent):
    """Agent specialised in contract analysis and JSON serialisation."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or CONTRACT_AGENT_PROMPT
        base_cfg.max_iterations = 12
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core document tools + contract-enhanced tools."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        if hasattr(self.tool_kit, "extract_contract_data"):
            self.registry.register(
                Tool(
                    name="extract_contract_data",
                    description=(
                        "Extract structured contract data (parties, dates, "
                        "clauses, obligations, risks) as JSON. Best for "
                        "text-based PDFs."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "doc_name": {
                                "type": "string",
                                "description": "Name of the document file.",
                            },
                        },
                        "required": ["doc_name"],
                    },
                    func=self.tool_kit.extract_contract_data,
                )
            )

        if hasattr(self.tool_kit, "ocr_extract_contract"):
            self.registry.register(
                Tool(
                    name="ocr_extract_contract",
                    description=(
                        "Use vision-based OCR to extract structured contract data "
                        "from scanned PDFs. Returns JSON. Use when extract_contract_data "
                        "fails or the PDF is a scan."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "doc_name": {
                                "type": "string",
                                "description": "Name of the document file.",
                            },
                            "page_num": {
                                "type": "integer",
                                "description": "Optional specific page number (1-indexed).",
                                "default": None,
                            },
                        },
                        "required": ["doc_name"],
                    },
                    func=self.tool_kit.ocr_extract_contract,
                )
            )

        if hasattr(self.tool_kit, "calculate"):
            self.registry.register(
                Tool(
                    name="calculate",
                    description=(
                        "Evaluate a mathematical expression with numbers from "
                        "the contract. Use for payment amounts, durations, etc."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Math expression, e.g. '50000 * 3'",
                            },
                        },
                        "required": ["expression"],
                    },
                    func=self.tool_kit.calculate,
                )
            )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        return response
