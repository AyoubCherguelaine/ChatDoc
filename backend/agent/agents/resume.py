"""
Resume and talent intelligence agent.

Specialises in parsing resumes, CVs, portfolios, and candidate profiles.
Extracts contact info, skills taxonomy, work history, education, and seniority scores.
Presents structured candidate profiles.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

RESUME_AGENT_PROMPT = """\
You are an AI Talent Intelligence and Resume Parsing Agent.
Your objective is to evaluate resumes, CVs, and professional biographies to extract
candidate qualifications, skills taxonomies, experience timelines, and seniority indicators.

Capabilities:
- Candidate contact: full name, email, phone number, location, portfolio/GitHub/LinkedIn links.
- Profile summary: professional headline and executive bio.
- Skills taxonomy: technical competencies, programming languages, cloud platforms, tools, and soft skills.
- Experience breakdown: companies, titles, tenure dates, responsibilities, quantifiable achievements.
- Education & Certifications: institutions, degrees, fields of study, graduation years, industry credentials.
- Seniority & fit assessment: estimated total years of relevant experience and candidate seniority level.

Process:
1. Examine document content using read_page or list_documents.
2. Use extract_resume_data to extract structured candidate details.
3. Organize findings into structured Markdown sections and include the raw JSON data block.
4. Highlight candidate strengths and potential alignment for hiring evaluation.
"""


class ResumeAgent(BaseAgent):
    """Agent specialised in resume and CV talent intelligence extraction."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or RESUME_AGENT_PROMPT
        base_cfg.max_iterations = 10
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core document tools + resume tools."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        if hasattr(self.tool_kit, "extract_resume_data"):
            self.registry.register(
                Tool(
                    name="extract_resume_data",
                    description=(
                        "Extract structured resume / CV data (candidate contact, summary, skills, "
                        "work history, education, certifications, seniority level) as JSON."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "doc_name": {"type": "string", "description": "Name of the document file."},
                        },
                        "required": ["doc_name"],
                    },
                    func=self.tool_kit.extract_resume_data,
                )
            )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        """Ensure clean output formatting."""
        cleaned = response.strip()
        if not cleaned.startswith(("#", "##")):
            return f"## Talent & Resume Intelligence\n\n{cleaned}"
        return cleaned
