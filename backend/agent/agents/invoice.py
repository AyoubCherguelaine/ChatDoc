"""
Invoice processing agent.

Specialises in extracting structured invoice data from PDF invoices and
presenting it as clean JSON.  Identifies line items, totals, taxes,
payment terms, vendor / client details, and due dates.

Uses :class:`EnhancedDocumentKit` for enhanced invoice-specific tools.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

INVOICE_AGENT_PROMPT = """\
You are an invoice processing agent. Your job is to extract structured data
from invoices and present it as clean JSON.

You can identify and extract:
- Invoice number and date
- Vendor name, address, and contact info
- Client / bill-to name, address, and contact info
- Line items (description, quantity, unit price, total)
- Subtotal, tax amounts, tax rates, and grand total
- Payment terms (due date, method, reference)
- Currency and any purchase order (PO) numbers

Process:
1. Search the document for invoice-related content.
2. Use extract_invoice_data to pull structured fields.
3. Use calculate to verify totals (e.g., subtotal + tax = total).
4. Present results as a JSON object with source citations.
5. If the document is not an invoice, report that and switch to general
   document Q&A using your search tools.
"""


class InvoiceAgent(BaseAgent):
    """Agent specialised in invoice data extraction and JSON serialisation."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or INVOICE_AGENT_PROMPT
        base_cfg.max_iterations = 10
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core document tools + invoice-enhanced tools."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        if hasattr(self.tool_kit, "extract_invoice_data"):
            self.registry.register(
                Tool(
                    name="extract_invoice_data",
                    description=(
                        "Extract structured invoice data (vendor, client, line "
                        "items, totals, taxes, payment terms) as JSON. Best for "
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
                    func=self.tool_kit.extract_invoice_data,
                )
            )

        if hasattr(self.tool_kit, "ocr_extract_invoice"):
            self.registry.register(
                Tool(
                    name="ocr_extract_invoice",
                    description=(
                        "Use vision-based OCR to extract structured invoice data "
                        "from scanned PDFs. Returns JSON. Use when extract_invoice_data "
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
                    func=self.tool_kit.ocr_extract_invoice,
                )
            )

        if hasattr(self.tool_kit, "calculate"):
            self.registry.register(
                Tool(
                    name="calculate",
                    description=(
                        "Evaluate a mathematical expression with numbers from "
                        "the invoice. Use to verify totals, compute taxes, etc."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Math expression, e.g. '1250.00 + 100.00'",
                            },
                        },
                        "required": ["expression"],
                    },
                    func=self.tool_kit.calculate,
                )
            )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        # If the response already looks like JSON, ensure it has a trailing
        # note about source verification.
        if response.strip().startswith("{"):
            return response
        return response
