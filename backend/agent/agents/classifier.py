"""
Bilingual Document Classifier & Intelligent Triage Agent.

Specialises in classifying documents into enterprise categories in English & Arabic:
Invoices, Contracts, Financial Statements, Resumes, Commercial Registrations, Official Letters.
Determines language, urgency priority, and target routing department.
"""

from __future__ import annotations

import json
from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.bilingual import BilingualDocumentKit
from backend.agent.tools.registry import Tool

CLASSIFIER_AGENT_PROMPT = """\
You are an Enterprise Document Classification and Automated Triage Specialist fluent in English and Arabic.
Your objective is to inspect incoming documents, determine their document type, primary language,
routing department, and urgency level.

Categories supported:
- Tax Invoice / فاتورة ضريبية
- Legal Contract / عقد أو اتفاقية
- Financial Statement / قوائم مالية
- Resume / سيرة ذاتية
- Commercial Registration (CR) / سجل تجاري
- Official Letter / Government Circular / خطاب رسمي أو تعميم
- General Business Document / مستند عام

Process:
1. Inspect the document layout and content using read_page or search_documents.
2. Run classify_document to evaluate category patterns and language statistics.
3. Structure your response into:
   - ## Document Classification Summary (ملخص تصنيف المستند)
   - **Document Type (نوع المستند)**: Category in EN and AR
   - **Language (لغة المستند)**: Arabic, English, or Bilingual
   - **Routing Department (القسم المستهدف)**: Target department
   - **Priority & Urgency (درجة الأهمية)**: Normal or Urgent
   - **Key Extracted Metadata (أهم البيانات المكتشفة)**: Entity names, dates, references
"""


class ClassifierAgent(BaseAgent):
    """Agent specialised in bilingual document classification and enterprise routing."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or CLASSIFIER_AGENT_PROMPT
        base_cfg.max_iterations = 8
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register document tools + classifier tool."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        self.registry.register(
            Tool(
                name="classify_document",
                description="Classify document category, language, and routing department in Arabic and English.",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Document text snippet."},
                    },
                    "required": ["text"],
                },
                func=lambda text: json.dumps(BilingualDocumentKit.classify_document(text), ensure_ascii=False),
            )
        )

