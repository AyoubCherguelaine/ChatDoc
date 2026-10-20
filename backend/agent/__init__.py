"""
Agent package — free autonomous agent with document tools and ReAct loops.

Submodules
----------
agent.py
    The :class:`FreeAgent` core: a ReAct-style loop that can call tools
    iteratively until it can answer the user's question.

tools.document_tools
    Concrete tools for reading pages, searching, summarising, etc.

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
