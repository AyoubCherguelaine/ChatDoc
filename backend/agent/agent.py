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

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentConfig:
    """Configuration for :class:`FreeAgent`."""

    max_iterations: int = 10
    verbose: bool = True
    stop_after_no_action: bool = True  # Stop if LLM doesn't suggest a tool
    temperature: Optional[float] = None


@dataclass
class AgentResult:
    """Result of an agent run."""

    response: str
    steps: list[dict] = field(default_factory=list)
    success: bool = True
    iterations: int = 0
    error: Optional[str] = None


class FreeAgent:
    """
    A free ReAct agent that uses document tools in a loop.

    Parameters
    ----------
    llm
        Any LangChain-compatible LLM or ChatModel.
    tool_kit
        A :class:`~agent.tools.document_tools.DocumentToolKit` instance.
    config
        Agent configuration.
    """

    def __init__(
        self,
        llm: Any,
        tool_kit: Any,
        config: Optional[AgentConfig] = None,
    ):
        self.llm = llm
        self.tool_kit = tool_kit
        self.config = config or AgentConfig()

        # Build the tool registry from the kit
        from backend.agent.tools.registry import ToolRegistry

        self.registry = ToolRegistry()
        if hasattr(tool_kit, "register_all"):
            tool_kit.register_all(self.registry)
        elif isinstance(tool_kit, ToolRegistry):
            self.registry = tool_kit
        else:
            raise ValueError("tool_kit must be a DocumentToolKit with register_all() or a ToolRegistry")

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def run(self, query: str) -> AgentResult:
        """Execute the ReAct loop synchronously."""
        steps: list[dict] = []

        for iteration in range(1, self.config.max_iterations + 1):
            prompt = self._build_prompt(query, steps)
            llm_response = self._call_llm(prompt)
            parsed = self._parse(llm_response)

            if self.config.verbose:
                self._log_step(iteration, parsed, llm_response)

            steps.append(
                {
                    "thought": parsed["thought"],
                    "action": parsed["action"],
                    "params": parsed["params"],
                    "llm_output": llm_response,
                    "observation": "",  # filled below
                }
            )

            # --- Final answer ---
            if parsed["action"] == "FINAL":
                steps[-1]["observation"] = ""
                return AgentResult(
                    response=parsed["response"],
                    steps=steps,
                    success=True,
                    iterations=iteration,
                )

            # --- Tool call ---
            observation = self._execute_tool(parsed["action"], parsed["params"])
            steps[-1]["observation"] = observation

            # Check if the agent is stuck (no observation)
            if not observation or observation.startswith("ERROR:"):
                if self.config.stop_after_no_action:
                    self._log(f"  Agent stopped: no valid tool result for '{parsed['action']}'")
                    return AgentResult(
                        response=self._fallback_response(query, steps, observation),
                        steps=steps,
                        success=False,
                        iterations=iteration,
                        error=observation,
                    )

        # Max iterations reached
        self._log("  Agent reached max iterations without a final answer.")
        return AgentResult(
            response=self._fallback_response(query, steps),
            steps=steps,
            success=False,
            iterations=self.config.max_iterations,
            error="Max iterations reached without a final answer.",
        )

    async def arun(self, query: str) -> AgentResult:
        """Execute the ReAct loop asynchronously."""
        steps: list[dict] = []

        for iteration in range(1, self.config.max_iterations + 1):
            prompt = self._build_prompt(query, steps)
            llm_response = await self._call_llm_async(prompt)
            parsed = self._parse(llm_response)

            if self.config.verbose:
                self._log_step(iteration, parsed, llm_response)

            steps.append(
                {
                    "thought": parsed["thought"],
                    "action": parsed["action"],
                    "params": parsed["params"],
                    "llm_output": llm_response,
                    "observation": "",
                }
            )

            if parsed["action"] == "FINAL":
                steps[-1]["observation"] = ""
                return AgentResult(
                    response=parsed["response"],
                    steps=steps,
                    success=True,
                    iterations=iteration,
                )

            observation = await self._execute_tool_async(parsed["action"], parsed["params"])
            steps[-1]["observation"] = observation

        return AgentResult(
            response=self._fallback_response(query, steps),
            steps=steps,
            success=False,
            iterations=self.config.max_iterations,
            error="Max iterations reached without a final answer.",
        )

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_prompt(self, query: str, steps: list[dict]) -> str:
        from backend.agent.prompts import (
            REACT_PROMPT,
            SYSTEM_PROMPT,
            format_scratchpad,
        )

        tool_desc = self.registry.format_tool_descriptions()
        tool_names = ", ".join(self.registry.tool_names)
        scratchpad = format_scratchpad(steps)

        return REACT_PROMPT.format(
            system_prompt=SYSTEM_PROMPT,
            tool_descriptions=tool_desc,
            query=query,
            scratchpad=scratchpad,
            tool_names=tool_names,
        )

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the full prompt and return raw text."""
        if hasattr(self.llm, "invoke"):
            result = self.llm.invoke(prompt)
            if hasattr(result, "content"):
                return result.content
            if isinstance(result, str):
                return result
            return str(result)
        if hasattr(self.llm, "predict"):
            return self.llm.predict(prompt)
        raise RuntimeError("LLM must have invoke() or predict() method.")

    async def _call_llm_async(self, prompt: str) -> str:
        """Async version of _call_llm."""
        if hasattr(self.llm, "ainvoke"):
            result = await self.llm.ainvoke(prompt)
            if hasattr(result, "content"):
                return result.content
            if isinstance(result, str):
                return result
            return str(result)
        # Fallback: run sync
        return self._call_llm(prompt)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(self, name: str, params: dict) -> str:
        return self.registry.execute(name, params)

    async def _execute_tool_async(self, name: str, params: dict) -> str:
        return await self.registry.aexecute(name, params)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self, text: str) -> dict:
        from backend.agent.prompts import parse_agent_output

        parsed = parse_agent_output(text)

        # Normalize action to match registered tool names
        action = parsed["action"]
        if action != "FINAL" and action not in self.registry.tool_names:
            # Try case-insensitive or prefix match
            for name in self.registry.tool_names:
                lower_action = action.lower()
                if lower_action == name.lower() or name.lower().startswith(lower_action):
                    parsed["action"] = name
                    break
            else:
                parsed["action"] = action  # let it fail in execute

        return parsed

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    def _fallback_response(
        self,
        query: str,
        steps: list[dict],
        error: str = "",
    ) -> str:
        """Generate a fallback answer when the agent can't reach FINAL."""
        snippets = []
        for step in steps:
            obs = step.get("observation", "")
            if obs and not obs.startswith("ERROR"):
                snippets.append(obs[:500])

        if snippets:
            combined = "\n\n".join(snippets)
            if self.llm is not None:
                try:
                    fallback_prompt = (
                        f"Based on the following search results and "
                        f"the user's question, provide a concise answer:\n\n"
                        f"Results:\n{combined[:2000]}\n\n"
                        f"Question: {query}\nAnswer:"
                    )
                    return self._call_llm(fallback_prompt)
                except Exception:
                    pass

            return (
                f"Based on my search through the documents, here's what I found:\n\n"
                f"{combined[:1500]}\n\n"
                f"(I was unable to reach a definitive conclusion after "
                f"{len(steps)} iterations." + (f" Error: {error}" if error else "") + ")"
            )

        return (
            f"I couldn't find enough information to answer your question"
            f" about '{query}'. Please check that the documents are loaded "
            f"and try rephrasing your question."
        )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, msg: str) -> None:
        if self.config.verbose:
            print(msg)

    def _log_step(self, iteration: int, parsed: dict, raw: str) -> None:
        from backend.agent.prompts import parse_agent_output  # noqa

        self._log(f"\n{'=' * 60}")
        self._log(f"Iteration {iteration}")
        self._log(f"{'=' * 60}")
        self._log(f"Thought: {parsed['thought']}")
        self._log(f"Action:  {parsed['action']}")
        if parsed["params"]:
            self._log(f"Params:  {json.dumps(parsed['params'])}")
        if parsed["action"] == "FINAL":
            self._log(f"Response: {parsed['response'][:200]}...")
