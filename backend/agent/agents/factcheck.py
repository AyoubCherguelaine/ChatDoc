"""
Fact-checking agent.

Specialises in verifying specific claims against document evidence. Uses
the ``verify_fact`` tool to gather evidence and classify claims as
supported, contradicted, or undetermined.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

FACTCHECK_AGENT_PROMPT = """\
You are a fact-checking agent. Your job is to verify claims against the
document evidence and report whether each claim is SUPPORTED, CONTRADICTED,
or UNDETERMINED.

Process:
1. Search the documents for the key terms in the claim.
2. Read the cited pages to find the exact evidence.
3. Use verify_fact to gather evidence and get an assessment.
4. Report your verdict with source citations.

Rules:
- Be precise: "Supported with high confidence" vs "Partially supported"
- If the documents don't contain the information, say "Undetermined"
- Cite the specific page/section where evidence was found
- If evidence contradicts the claim, quote the contradicting passage
"""


class FactCheckAgent(BaseAgent):
    """Agent specialised in claim verification and fact-checking."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or FACTCHECK_AGENT_PROMPT
        base_cfg.max_iterations = 6
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core tools + verify_fact."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        # Add verify_fact if the enhanced kit is available
        if hasattr(self.tool_kit, "verify_fact"):
            self.registry.register(
                Tool(
                    name="verify_fact",
                    description=(
                        "Search the documents for evidence that supports or "
                        "contradicts a specific claim. Returns an LLM-based "
                        "assessment with citations."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "claim": {"type": "string", "description": "The claim to verify."},
                            "top_k": {"type": "integer", "description": "Number of evidence docs to retrieve.", "default": 10},
                        },
                        "required": ["claim"],
                    },
                    func=self.tool_kit.verify_fact,
                )
            )
