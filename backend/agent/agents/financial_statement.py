"""
Bilingual Financial Statement Analyzer Agent.

Specialises in extracting balance sheet, income statement (P&L), and cash flow items,
calculating key financial ratios (Gross Margin, Net Margin, Debt-to-Equity),
and supporting Arabic and English accounting frameworks (SOCPA, IFRS, GAAP).
"""

from __future__ import annotations

import json
from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.bilingual import BilingualDocumentKit
from backend.agent.tools.registry import Tool

FINANCIAL_STATEMENT_PROMPT = """\
You are an Enterprise Corporate Finance & Financial Statement Intelligence Specialist fluent in English and Arabic.
Your objective is to extract and analyze balance sheets, income statements (P&L),
and cash flow statements under IFRS, SOCPA, and GAAP frameworks.

Line items to extract:
- Revenue / الإيرادات والمبيعات
- Cost of Goods Sold (COGS) / تكلفة المبيعات
- Gross Profit / إجمالي الربح
- Operating Expenses / المصروفات التشغيلية
- Operating Income (EBIT) / الربح التشغيلي
- Net Income / صافي الربح
- Total Assets / إجمالي الأصول (Current & Non-Current)
- Total Liabilities / إجمالي الخصوم (Current & Long-Term)
- Shareholders' Equity / حقوق المساهمين

Financial Ratios to compute:
- Gross Margin % (هامش إجمالي الربح)
- Net Profit Margin % (هامش صافي الربح)
- Debt-to-Equity Ratio (نسبة الدين إلى حقوق الملكية)
- Debt-to-Assets Ratio (نسبة الدين إلى الأصول)

Process:
1. Locate financial tables using search_documents or read_page.
2. Run analyze_financial_statement to extract financial metrics and calculate ratios.
3. Present your findings clearly with:
   - ## Financial Overview (نظرة عامة على القوائم المالية)
   - ## Income Statement Analysis (تحليل قائمة الدخل والأرباح)
   - ## Balance Sheet & Solvency (الميزانية العمومية والسيولة)
   - ## Key Financial Ratios (أبرز النسب المالية)
   - Cite source pages for all figures.
"""


class FinancialStatementAgent(BaseAgent):
    """Agent specialised in bilingual financial statement extraction and ratio analysis."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or FINANCIAL_STATEMENT_PROMPT
        base_cfg.max_iterations = 10
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register document tools + financial statement tool."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        self.registry.register(
            Tool(
                name="analyze_financial_statement",
                description="Extract financial metrics (revenue, profit, assets, liabilities) and calculate ratios.",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Financial statement text or table content."},
                    },
                    "required": ["text"],
                },
                func=lambda text: json.dumps(BilingualDocumentKit.analyze_financial_statement(text), ensure_ascii=False),
            )
        )

