"""
Compliance, privacy audit, and PII anonymizer agent.

Specialises in inspecting documents for Personally Identifiable Information (PII),
GDPR/HIPAA compliance exposures, secret leaks, and producing redaction previews.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

COMPLIANCE_AGENT_PROMPT = """\
You are an Enterprise Privacy, Compliance, and Data Governance Agent.
Your objective is to audit documents for Personally Identifiable Information (PII),
confidential secrets, and regulatory compliance risks under GDPR, HIPAA, and CCPA standards.

Capabilities:
- Sensitive PII detection: SSNs, national identification numbers, credit card/IBAN accounts, emails, phone numbers, addresses.
- Credential leaks: API keys, passwords, database URLs, auth tokens.
- Protected Health Information (PHI) under HIPAA regulations.
- Risk Scoring: Compute a risk rating (Low, Medium, High, Critical) with itemized findings and source pages.
- Redaction Preview: Supply clear recommendations and an anonymized preview of sensitive passages.

Process:
1. Search and inspect the document using search_documents and read_page.
2. Use audit_document_compliance to generate the comprehensive risk evaluation.
3. Structure findings into clearly organized audit sections:
   - ## Compliance Audit Overview & Score
   - ## Detected PII & Sensitive Findings
   - ## Regulatory Implications (GDPR / HIPAA)
   - ## Remediation & Redaction Guidance
4. Always cite specific locations (page numbers or sections) for every finding.
"""


class ComplianceAgent(BaseAgent):
    """Agent specialised in compliance auditing, PII detection, and redaction guidance."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or COMPLIANCE_AGENT_PROMPT
        base_cfg.max_iterations = 10
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core document tools + compliance tools."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        if hasattr(self.tool_kit, "audit_document_compliance"):
            self.registry.register(
                Tool(
                    name="audit_document_compliance",
                    description=(
                        "Audit document for PII, GDPR/HIPAA compliance risks, sensitive data, "
                        "and produce risk scoring and redaction preview."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "doc_name": {"type": "string", "description": "Name of the document file."},
                        },
                        "required": ["doc_name"],
                    },
                    func=self.tool_kit.audit_document_compliance,
                )
            )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        """Ensure clean output formatting."""
        cleaned = response.strip()
        if not cleaned.startswith(("#", "##")):
            return f"## PII & Compliance Audit\n\n{cleaned}"
        return cleaned
