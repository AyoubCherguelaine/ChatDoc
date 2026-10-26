"""
Receipt and expense intelligence agent.

Specialises in parsing receipts, meal vouchers, travel expenses, and invoices.
Extracts merchant data, itemized expenses, tax breakdowns, tips, and categories.
Presents verified structured JSON output.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

RECEIPT_AGENT_PROMPT = """\
You are an expert Receipt and Expense Intelligence Agent.
Your job is to extract itemized financial data from receipts, restaurant slips, travel expenses,
and utility bills, presenting verified structured JSON.

Capabilities:
- Merchant details: store name, address, phone, tax/VAT ID.
- Transaction metadata: date, time, receipt ID, currency, payment method (cash, card brand, last 4 digits).
- Line items: item description, quantity, unit price, total price, expense category.
- Financial totals: subtotal, taxes (rate & amount), tips, grand total.
- Verification: calculate and confirm that items sum to subtotal, and subtotal + tax + tip equals grand total.

Process:
1. Search and inspect the document for receipt or payment evidence.
2. Use extract_receipt_data to obtain structured expense fields as JSON.
3. Use calculate to double-check mathematical totals.
4. If scanned or vision-needed, utilize ocr_read_page.
5. Present final results as a clean JSON block accompanied by an executive expense breakdown and citations.
"""


class ReceiptAgent(BaseAgent):
    """Agent specialised in receipt, expense, and transaction extraction."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or RECEIPT_AGENT_PROMPT
        base_cfg.max_iterations = 10
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core document tools + receipt-specific tools."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        if hasattr(self.tool_kit, "extract_receipt_data"):
            self.registry.register(
                Tool(
                    name="extract_receipt_data",
                    description=(
                        "Extract structured receipt and expense data (merchant, date, line items, "
                        "taxes, tip, payment method, category) as JSON."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "doc_name": {"type": "string", "description": "Name of the document file."},
                        },
                        "required": ["doc_name"],
                    },
                    func=self.tool_kit.extract_receipt_data,
                )
            )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        """Ensure clean output formatting."""
        cleaned = response.strip()
        if not cleaned.startswith(("#", "##")):
            return f"## Receipt & Expense Intelligence\n\n{cleaned}"
        return cleaned
