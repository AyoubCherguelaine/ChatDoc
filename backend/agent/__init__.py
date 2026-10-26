"""
Agent package — free autonomous agent with document tools and ReAct loops,
plus a specialised multi-agent system.

Submodules
----------
agent.py
    The :class:`FreeAgent` core: a ReAct-style loop that can call tools
    iteratively until it can answer the user's question.

agents/
    Specialised agent implementations:

    * :class:`~backend.agent.agents.base.BaseAgent` — abstract ReAct base
    * :class:`~backend.agent.agents.summary.SummaryAgent` — executive summaries
    * :class:`~backend.agent.agents.research.ResearchAgent` — deep research
    * :class:`~backend.agent.agents.extraction.ExtractionAgent` — data extraction
    * :class:`~backend.agent.agents.comparison.ComparisonAgent` — document comparison
    * :class:`~backend.agent.agents.factcheck.FactCheckAgent` — claim verification
    * :class:`~backend.agent.agents.coordinator.CoordinatorAgent` — routing

tools.document_tools
    Concrete tools for reading pages, searching, summarising, etc.

tools.enhanced
    Extended tools: extract_table, verify_fact, calculate, get_outline.

tools.registry
    Base :class:`Tool` dataclass and :class:`ToolRegistry` container.

prompts
    Prompt templates for the ReAct loop and system instructions.
"""

from .agent import AgentConfig, AgentResult, FreeAgent
from .prompts import REACT_PROMPT, SYSTEM_PROMPT
from .tools.document_tools import DocumentToolKit
from .tools.registry import Tool, ToolRegistry

__all__ = [
    "FreeAgent",
    "AgentConfig",
    "AgentResult",
    "DocumentToolKit",
    "Tool",
    "ToolRegistry",
    "REACT_PROMPT",
    "SYSTEM_PROMPT",
]
