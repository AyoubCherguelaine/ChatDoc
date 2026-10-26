"""
Bilingual Redaction & Document Sanitization Agent.

Specialises in anonymizing and redacting sensitive PII in English & Arabic:
National IDs, Saudi Iqama, IBANs, Credit Cards, VAT/TIN, Phone numbers, and addresses.
"""

from __future__ import annotations

import json
from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.bilingual import BilingualDocumentKit
from backend.agent.tools.registry import Tool

REDACTION_AGENT_PROMPT = """\
You are an Enterprise Privacy & Document Redaction Specialist fluent in English and Arabic.
Your objective is to inspect documents, identify Personally Identifiable Information (PII)
and confidential entities (National IDs, Civil IDs, Saudi Iqama, GCC IBANs, Tax IDs, Credit Cards,
personal phone numbers, and home addresses), and provide a fully sanitized, safe version.

Capabilities:
- Bilingual PII sanitization in both English and Arabic.
- Masks entities with clear tokens (e.g., [REDACTED_NATIONAL_ID / هوية_محجوبة], [REDACTED_IBAN / آيبان_محجوب]).
- Generates an itemized audit log of redacted items.
- Preserves business context and non-confidential clauses.

Process:
1. Read the document sections using read_page or search_documents.
2. Run redact_pii to automatically identify and mask known PII patterns.
3. Review context for any names, signatures, or confidential references that need masking.
4. Provide structured output:
   - ## Redaction Audit Summary (ملخص التطهير والحجب)
   - ## Sanitized Document Text (النص المطهر الآمن)
   - ## Redacted Entities Log (سجل البيانات المحجوبة)
"""


class RedactionAgent(BaseAgent):
    """Agent specialised in bilingual PII redaction and document sanitization."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or REDACTION_AGENT_PROMPT
        base_cfg.max_iterations = 10
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register document tools + redaction tool."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        self.registry.register(
            Tool(
                name="redact_pii",
                description="Redact and mask sensitive PII in Arabic and English text.",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to redact."},
                    },
                    "required": ["text"],
                },
                func=lambda text: json.dumps(BilingualDocumentKit.redact_pii(text), ensure_ascii=False),
            )
        )

