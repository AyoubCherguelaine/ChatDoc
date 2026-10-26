"""
Executive summary agent.

Specialises in producing concise, well-structured summaries of documents.
Uses page reading and search tools iteratively to build a complete picture
before condensing into a final summary with key points and citations.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig

SUMMARY_AGENT_PROMPT = """\
You are a summarisation agent. Your job is to read the document thoroughly,
identify the key points, and produce a concise executive summary.

Guidelines:
1. Start by listing available documents to understand what you have.
2. Read the most important pages (beginning, middle, end) to grasp the content.
3. Search for key topics: purpose, findings, conclusions, recommendations.
4. Condense everything into a structured summary with clear headings.
5. Cite the source document and page number for every key claim.
6. Do not invent content — only include what the documents actually say.

Respond with FINAL only when you have read enough to give a confident summary.
"""


class SummaryAgent(BaseAgent):
    """Agent specialised in executive document summaries."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or SUMMARY_AGENT_PROMPT
        base_cfg.max_iterations = 8
        super().__init__(llm, tool_kit, base_cfg)

    def _post_process(self, response: str, steps: list[dict]) -> str:
        # Ensure the summary has a clear structure
        if not response.strip().startswith(("#", "##", "Executive")):
            intro = "## Executive Summary\n\n"
            if not response.strip().startswith("#"):
                response = intro + response.strip()
        return response
