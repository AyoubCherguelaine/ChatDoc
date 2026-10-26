"""
Free autonomous agent with ReAct loops.

The :class:`FreeAgent` implements a classic ReAct loop:

    Thought → Action (tool call) → Observation → repeat → Final answer

Unlike a fixed retrieval chain, the agent can:

* Search the vector store with arbitrary queries
* Read specific pages to verify or extract detail
* Summarise long passages
* Compare information across documents
* Ask follow-up questions of itself (the LLM)

The agent is "free" in that it is not constrained to a single
retrieval-then-answer pattern — it can take as many tool calls as
needed (up to ``max_iterations``) to reach a confident answer.

Example::

    agent = FreeAgent(llm=llm, tool_kit=tool_kit)
    result = agent.run("What are the main differences between Document A and B?")
    print(result.response)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.agent.agents.base import AgentResult as _AgentResult
from backend.agent.agents.base import BaseAgent, BaseAgentConfig

# Re-export for backward compatibility
AgentResult = _AgentResult


@dataclass
class AgentConfig:
    """Configuration for :class:`FreeAgent`.

    Backwards-compatible with the original dataclass.  When passed to
    :class:`FreeAgent`, it is converted to a :class:`~backend.agent.agents.base.BaseAgentConfig`.
    """

    max_iterations: int = 10
    verbose: bool = True
    stop_after_no_action: bool = True
    temperature: Optional[float] = None
    system_prompt: str = ""


class FreeAgent(BaseAgent):
    """
    A free ReAct agent that uses document tools in a loop.

    Parameters
    ----------
    llm
        Any LangChain-compatible LLM or ChatModel.
    tool_kit
        A :class:`~agent.tools.document_tools.DocumentToolKit` instance.
    config
        Agent configuration.  Accepts the legacy :class:`AgentConfig`
        or a :class:`~backend.agent.agents.base.BaseAgentConfig`.
    """

    def __init__(
        self,
        llm: Any,
        tool_kit: Any,
        config: Optional[AgentConfig] = None,
    ):
        # Convert legacy AgentConfig to BaseAgentConfig
        if config is not None and isinstance(config, AgentConfig):
            base_cfg = BaseAgentConfig(
                max_iterations=config.max_iterations,
                verbose=config.verbose,
                stop_after_no_action=config.stop_after_no_action,
                temperature=config.temperature,
                system_prompt=config.system_prompt,
            )
        elif config is not None and isinstance(config, BaseAgentConfig):
            base_cfg = config
        else:
            base_cfg = BaseAgentConfig()

        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register document tools from the kit."""
        from backend.agent.tools.registry import ToolRegistry

        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)
        elif isinstance(self.tool_kit, ToolRegistry):
            self.registry = self.tool_kit
        else:
            raise ValueError(
                "tool_kit must be a DocumentToolKit with register_all() or a ToolRegistry"
            )
