"""
Coordinator agent — multi-agent routing and orchestration.

The :class:`CoordinatorAgent` is the top-level agent that receives a user
question, determines which specialised agent is best suited to answer it,
delegates the task, and synthesises the results.

It works by:
1. Parsing the question and deciding which specialist to invoke.
2. Calling a ``delegate`` tool with the specialist name and the question.
3. Receiving the specialist's full response as an observation.
4. Optionally invoking additional specialists for cross-checking.
5. Producing a final synthesised answer.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.agent.agents.base import AgentResult, BaseAgent, BaseAgentConfig
from backend.agent.tools.registry import Tool

COORDINATOR_PROMPT = """\
You are an Enterprise Multi-Agent Coordinator and Orchestrator. Your mission is to analyze the user's objective, route tasks to the optimal domain specialist agent, and synthesize high-confidence, source-verified results.

Available Specialist Agents:
- **invoice** — Extracts complete structured invoice data, line items, taxes, vendor/client, and arithmetic validation into JSON.
- **receipt** — Extracts itemized receipts, expense slips, payment methods, merchant metadata, and tips into JSON.
- **financial_statement** — Parses Balance Sheets and P&L statements, computes Gross Margin, Net Margin, and Debt-to-Equity ratios.
- **anomaly_audit** — Audits mathematical integrity, ZATCA / GCC 15% VAT accuracy, and date chronology to flag risk and anomalies.
- **contract** — Analyses legal agreements, termination clauses, indemnities, liability caps, and risk flags into JSON.
- **compliance** — Scans documents for GDPR/HIPAA exposures, credentials, and sensitive PII with severity risk scoring.
- **redaction** — Bilingual masking of Saudi National IDs, GCC IBANs, and ZATCA VAT IDs in Arabic and English text.
- **form_parser** — Extracts key-value field pairs, checkbox states [X], and signature blocks.
- **extraction** — Pulls complex unstructured tables, numerical matrices, and metrics into Markdown or JSON tables.
- **classifier** — Categorizes document type, detects language (EN/AR), and sets target routing department.
- **resume** — Parses talent profiles, skills taxonomy, career history, and seniority assessment.
- **translation** — High-fidelity bidirectional translation between Arabic and English preserving legal and financial terminology.
- **summary** — Produces structured executive briefs covering purpose, key findings, and action items.
- **research** — Deep multi-step investigation cross-referencing evidence and citations across document sections.
- **google_ai** — Multimodal document intelligence and layout hierarchy analysis.
- **chat** — Conversational document Q&A with source citations.

Orchestration Rules:
1. Identify document context and analytical intent.
2. Delegate using the ``delegate`` tool with the precise specialist agent name and focused prompt.
3. For compound tasks (e.g., audit and redact, or extract table and summarize), delegate to relevant specialists sequentially and synthesize the verified outputs.
4. Always cite source document and page references.
"""


class CoordinatorAgent(BaseAgent):
    """
    Multi-agent coordinator that routes questions to specialist agents.

    Parameters
    ----------
    llm
        LLM instance (shared with sub-agents).
    tool_kit
        The :class:`DocumentToolKit` or :class:`EnhancedDocumentKit` bound
        to the current document index.
    sub_agents
        A dict mapping specialist names to :class:`BaseAgent` instances.
        If not provided, sub-agents are created lazily on first use.
    config
        Agent configuration (defaults to a coordinator-friendly config).
    """

    def __init__(
        self,
        llm: Any,
        tool_kit: Any,
        sub_agents: Optional[dict[str, BaseAgent]] = None,
        config: Optional[BaseAgentConfig] = None,
    ):
        self._sub_agent_factories: dict[str, Any] = {}
        self._sub_agents: dict[str, BaseAgent] = sub_agents or {}

        base_cfg = config or BaseAgentConfig()
        base_cfg.system_prompt = base_cfg.system_prompt or COORDINATOR_PROMPT
        base_cfg.max_iterations = 8
        super().__init__(llm, tool_kit, base_cfg)

    # ------------------------------------------------------------------
    # Sub-agent management
    # ------------------------------------------------------------------

    def register_sub_agent(self, name: str, agent: BaseAgent) -> "CoordinatorAgent":
        """Register a pre-built sub-agent instance."""
        self._sub_agents[name] = agent
        return self

    def register_sub_agent_factory(
        self, name: str, factory: Any
    ) -> "CoordinatorAgent":
        """Register a factory that creates a sub-agent on demand."""
        self._sub_agent_factories[name] = factory
        return self

    def _get_sub_agent(self, name: str) -> Optional[BaseAgent]:
        if name in self._sub_agents:
            return self._sub_agents[name]
        if name in self._sub_agent_factories:
            agent = self._sub_agent_factories[name]()
            self._sub_agents[name] = agent
            return agent
        return None

    @property
    def sub_agent_names(self) -> list[str]:
        names = list(self._sub_agents.keys())
        names.extend(self._sub_agent_factories.keys())
        return list(dict.fromkeys(names))

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        """Register document tools + the delegate tool."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

        self.registry.register(
            Tool(
                name="delegate",
                description=(
                    "Delegate the current sub-question to a specialised agent. "
                    "The specialist will search, read, and reason about the "
                    "documents, then return its full response."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "agent": {
                            "type": "string",
                             "enum": self.sub_agent_names or [
                                 "invoice", "receipt", "financial_statement", "anomaly_audit",
                                 "contract", "compliance", "redaction", "form_parser", "extraction",
                                 "classifier", "resume", "translation", "summary", "research",
                                 "google_ai", "chat",
                             ],
                            "description": "The specialist agent to delegate to.",
                        },
                        "query": {
                            "type": "string",
                            "description": "The sub-question or instruction for the specialist.",
                        },
                    },
                    "required": ["agent", "query"],
                },
                func=self._delegate,
            )
        )

    # ------------------------------------------------------------------
    # Delegate execution
    # ------------------------------------------------------------------

    def _delegate(self, agent: str, query: str) -> str:
        """Run a sub-agent and return its response as the observation."""
        sub = self._get_sub_agent(agent)
        if sub is None:
            available = ", ".join(self.sub_agent_names) or "none registered"
            return f"ERROR: Unknown agent '{agent}'. Available: {available}"

        try:
            result: AgentResult = sub.run(query)
            return result.response or "(no response from specialist)"
        except Exception as exc:
            return f"ERROR: Specialist '{agent}' failed: {exc}"

    async def _delegate_async(self, agent: str, query: str) -> str:
        sub = self._get_sub_agent(agent)
        if sub is None:
            available = ", ".join(self.sub_agent_names) or "none registered"
            return f"ERROR: Unknown agent '{agent}'. Available: {available}"

        try:
            result: AgentResult = await sub.arun(query)
            return result.response or "(no response from specialist)"
        except Exception as exc:
            return f"ERROR: Specialist '{agent}' failed: {exc}"

    # ------------------------------------------------------------------
    # Prompt building (override to include sub-agent list in prompt)
    # ------------------------------------------------------------------

    def _build_prompt(self, query: str, steps: list[dict]) -> str:
        from backend.agent.prompts import REACT_PROMPT, format_scratchpad

        tool_desc = self.registry.format_tool_descriptions()
        tool_names = ", ".join(self.registry.tool_names)
        scratchpad = format_scratchpad(steps)

        # Append sub-agent info to the system prompt
        system = self.config.system_prompt or COORDINATOR_PROMPT
        if self._sub_agents or self._sub_agent_factories:
            system = (
                system
                + "\n\nRegister specialists:\n"
                + "\n".join(
                    f"- {name}: registered"
                    for name in self.sub_agent_names
                )
            )

        return REACT_PROMPT.format(
            system_prompt=system,
            tool_descriptions=tool_desc,
            query=query,
            scratchpad=scratchpad,
            tool_names=tool_names,
        )

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _post_process(self, response: str, steps: list[dict]) -> str:
        """Synthesise the coordinator's answer, attributing to specialists."""
        # If the response doesn't mention sources, add a note
        if "[" not in response and "p." not in response:
            return response
        return response

    # ------------------------------------------------------------------
    # Convenience: one-call multi-agent processing
    # ------------------------------------------------------------------

    def run_with_routing(self, query: str) -> AgentResult:
        """
        Convenience method: the coordinator decides which specialist(s) to
        invoke and synthesises the final answer.
        """
        return self.run(query)
