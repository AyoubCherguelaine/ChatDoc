"""
Intelligent form parser agent.

Specialises in structured and semi-structured forms (applications, questionnaires,
government forms, tax declarations, insurance claims).
Extracts key-value fields, checkbox selections, tables, and signature states.
"""

from __future__ import annotations

from typing import Optional

from backend.agent.agents.base import BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

FORM_PARSER_AGENT_PROMPT = """\
You are an Intelligent Form Parser Agent.
Your objective is to extract key-value field pairs, checkbox selections, and signature status
from structured and semi-structured forms (applications, questionnaires, tax forms, insurance declarations).

Capabilities:
- Form identification: form title, form number, version, and date.
- Key-Value pairs: extract label-value relationships with high precision.
- Checkbox & Radio states: determine if options are selected [X] or unselected [ ].
- Signature blocks: identify signatory name, date signed, and signature presence.
- Table & Grid extraction: parse form grid structures into clean Markdown tables.

Process:
1. Examine document layout using get_outline or read_page.
2. Use extract_form_fields to obtain structured field mappings.
3. Organize into clear sections:
   - ## Form Information & Metadata
   - ## Key Fields & Values
   - ## Selection Options & Checkboxes
   - ## Signatures & Verifications
4. Mark any missing or required fields that were left blank.
"""


class FormParserAgent(BaseAgent):
    """Agent specialised in parsing form fields, checkboxes, and signatures."""

    def __init__(
        self,
        llm,
        tool_kit,
        config: Optional[BaseAgentConfig] = None,
    ):
        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or FORM_PARSER_AGENT_PROMPT
        base_cfg.max_iterations = 10
        super().__init__(llm, tool_kit, base_cfg)

    def _register_tools(self) -> None:
        """Register core document tools + form parsing tools."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        if hasattr(self.tool_kit, "extract_form_fields"):
            self.registry.register(
                Tool(
                    name="extract_form_fields",
                    description=(
                        "Extract key-value pairs, checkbox states, and signature information "
                        "from structured or semi-structured forms."
                    ),
                    parameters={
                        "type": "object",
                        "properties": {
                            "doc_name": {"type": "string", "description": "Name of the document file."},
                        },
                        "required": ["doc_name"],
                    },
                    func=self.tool_kit.extract_form_fields,
                )
            )

    def _post_process(self, response: str, steps: list[dict]) -> str:
        """Ensure clean output formatting."""
        cleaned = response.strip()
        if not cleaned.startswith(("#", "##")):
            return f"## Form Intelligence Extraction\n\n{cleaned}"
        return cleaned
