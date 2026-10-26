"""
Specialised agent implementations for document processing.

Each agent is a :class:`~backend.agent.agents.base.BaseAgent` subclass
with a tailored system prompt and tool set:

* :class:`SummaryAgent` — executive summaries
* :class:`ResearchAgent` — deep research with evidence gathering
* :class:`ExtractionAgent` — structured data extraction
* :class:`ComparisonAgent` — multi-document comparison
* :class:`FactCheckAgent` — claim verification
* :class:`InvoiceAgent` — invoice data extraction / JSON serialisation
* :class:`ContractAgent` — contract analysis and risk flagging
* :class:`GoogleAIDocumentAgent` — Google AI document intelligence and extraction
* :class:`ReceiptAgent` — receipt, expense, and transaction intelligence
* :class:`ResumeAgent` — resume and talent qualification analysis
* :class:`ComplianceAgent` — PII, GDPR/HIPAA risk and compliance audit
* :class:`FormParserAgent` — form field, checkbox, and signature parsing
* :class:`CoordinatorAgent` — routes questions to specialists
"""

from .anomaly_audit import AnomalyAuditAgent
from .base import AgentResult, BaseAgent, BaseAgentConfig
from .classifier import ClassifierAgent
from .comparison import ComparisonAgent
from .compliance import ComplianceAgent
from .contract import ContractAgent
from .coordinator import CoordinatorAgent
from .extraction import ExtractionAgent
from .factcheck import FactCheckAgent
from .financial_statement import FinancialStatementAgent
from .form_parser import FormParserAgent
from .google_ai import GoogleAIDocumentAgent
from .invoice import InvoiceAgent
from .receipt import ReceiptAgent
from .redaction import RedactionAgent
from .research import ResearchAgent
from .resume import ResumeAgent
from .summary import SummaryAgent
from .translation import TranslationAgent

__all__ = [
    "BaseAgent",
    "BaseAgentConfig",
    "AgentResult",
    "SummaryAgent",
    "ResearchAgent",
    "ExtractionAgent",
    "ComparisonAgent",
    "FactCheckAgent",
    "InvoiceAgent",
    "ContractAgent",
    "GoogleAIDocumentAgent",
    "ReceiptAgent",
    "ResumeAgent",
    "ComplianceAgent",
    "FormParserAgent",
    "CoordinatorAgent",
    "RedactionAgent",
    "ClassifierAgent",
    "FinancialStatementAgent",
    "TranslationAgent",
    "AnomalyAuditAgent",
]
