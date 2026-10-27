"""
Base agent framework for the multi-agent document processing system.

Provides :class:`BaseAgent` — a ReAct-style loop abstracted from the original
``FreeAgent`` so that specialised agents can share infrastructure while
customising their system prompt, tool set, and post-processing behaviour.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class BaseAgentConfig:
    """Configuration shared by all agent implementations."""

    max_iterations: int = 10
    verbose: bool = False
    stop_after_no_action: bool = True
    temperature: Optional[float] = None
    system_prompt: str = ""


@dataclass
class AgentResult:
    """Result returned by any agent after a run."""

    response: str
    steps: list[dict] = field(default_factory=list)
    success: bool = True
    iterations: int = 0
    error: Optional[str] = None


class BaseAgent:
    """
    Abstract ReAct agent base class.

    Subclasses override :meth:`_register_tools` to populate the
    :class:`ToolRegistry` and optionally set ``self.config.system_prompt``
    and :meth:`_post_process` for result refinement.

    The ReAct loop (shared with :class:`~backend.agent.agent.FreeAgent`)
    works as follows::

        Think → Action(tool) → Observation → repeat → FINAL
    """

    def __init__(
        self,
        llm: Any,
        tool_kit: Any,
        config: Optional[BaseAgentConfig] = None,
    ):
        self.llm = llm
        self.tool_kit = tool_kit
        self.config = config or BaseAgentConfig()
        self.registry = ToolRegistry()
        self._register_tools()

    # ------------------------------------------------------------------
    # Sub-classes
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        """Register the tools this agent can use. Override in sub-classes."""
        if hasattr(self.tool_kit, "register_all"):
            self.tool_kit.register_all(self.registry)

    def _build_prompt(self, query: str, steps: list[dict]) -> str:
        from backend.agent.prompts import REACT_PROMPT, SYSTEM_PROMPT, format_scratchpad

        system = self.config.system_prompt or SYSTEM_PROMPT
        tool_desc = self.registry.format_tool_descriptions()
        tool_names = ", ".join(self.registry.tool_names)
        scratchpad = format_scratchpad(steps)

        return REACT_PROMPT.format(
            system_prompt=system,
            tool_descriptions=tool_desc,
            query=query,
            scratchpad=scratchpad,
            tool_names=tool_names,
        )

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the full prompt and return raw text, with retries on transient errors."""
        last_exc: Optional[Exception] = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                if hasattr(self.llm, "invoke"):
                    result = self.llm.invoke(prompt)
                    if hasattr(result, "content"):
                        return result.content
                    return str(result)
                if hasattr(self.llm, "predict"):
                    return self.llm.predict(prompt)
                raise RuntimeError("LLM must have invoke() or predict() method.")
            except Exception as exc:
                last_exc = exc
                logger.warning("LLM call attempt %s/%s failed: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
        raise RuntimeError(f"LLM service call failed after {max_attempts} attempts: {last_exc}") from last_exc

    async def _call_llm_async(self, prompt: str) -> str:
        """Async version of _call_llm with retries on transient errors."""
        last_exc: Optional[Exception] = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                if hasattr(self.llm, "ainvoke"):
                    result = await self.llm.ainvoke(prompt)
                    if hasattr(result, "content"):
                        return result.content
                    return str(result)
                return self._call_llm(prompt)
            except Exception as exc:
                last_exc = exc
                logger.warning("Async LLM call attempt %s/%s failed: %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    import asyncio
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
        raise RuntimeError(f"Async LLM service call failed after {max_attempts} attempts: {last_exc}") from last_exc

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

        action = parsed["action"]
        if action != "FINAL" and action not in self.registry.tool_names:
            lower_action = action.lower()
            for name in self.registry.tool_names:
                if lower_action == name.lower() or name.lower().startswith(lower_action):
                    parsed["action"] = name
                    break
            else:
                parsed["action"] = action

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
        self._log(f"\n{'=' * 60}")
        self._log(f"Iteration {iteration}")
        self._log(f"{'=' * 60}")
        self._log(f"Thought: {parsed['thought']}")
        self._log(f"Action:  {parsed['action']}")
        if parsed["params"]:
            self._log(f"Params:  {json.dumps(parsed['params'])}")
        if parsed["action"] == "FINAL":
            self._log(f"Response: {parsed['response'][:200]}...")

    # ------------------------------------------------------------------
    # Core loop (synchronous)
    # ------------------------------------------------------------------

    def run(self, query: str) -> AgentResult:
        """Execute the ReAct loop synchronously with error resilience."""
        steps: list[dict] = []
        consecutive_errors = 0

        try:
            for iteration in range(1, self.config.max_iterations + 1):
                prompt = self._build_prompt(query, steps)
                try:
                    llm_response = self._call_llm(prompt)
                except Exception as exc:
                    self._log(f"  Agent error during LLM invocation: {exc}")
                    return AgentResult(
                        response=self._fallback_response(query, steps, error=str(exc)),
                        steps=steps,
                        success=False,
                        iterations=iteration,
                        error=f"LLM service error: {exc}",
                    )

                try:
                    parsed = self._parse(llm_response)
                except Exception as exc:
                    self._log(f"  Agent error parsing LLM response: {exc}")
                    parsed = {"thought": "Parsing fallback", "action": "FINAL", "params": {}, "response": llm_response}

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

                # --- Final answer ---
                if parsed["action"] == "FINAL":
                    steps[-1]["observation"] = ""
                    response = parsed["response"]
                    try:
                        response = self._post_process(response, steps)
                    except Exception as exc:
                        self._log(f"  Agent post-processing error: {exc}")
                    return AgentResult(
                        response=response,
                        steps=steps,
                        success=True,
                        iterations=iteration,
                    )

                # --- Tool call ---
                try:
                    observation = self._execute_tool(parsed["action"], parsed["params"])
                except Exception as exc:
                    observation = f"ERROR: Tool execution exception: {exc}"

                steps[-1]["observation"] = observation

                if not observation or observation.startswith("ERROR:"):
                    consecutive_errors += 1
                    if consecutive_errors >= 3 and self.config.stop_after_no_action:
                        self._log(f"  Agent stopped: repeated failed tool results for '{parsed['action']}'")
                        return AgentResult(
                            response=self._fallback_response(query, steps, observation),
                            steps=steps,
                            success=False,
                            iterations=iteration,
                            error=observation,
                        )
                else:
                    consecutive_errors = 0

            # Max iterations reached
            self._log("  Agent reached max iterations without a final answer.")
            return AgentResult(
                response=self._fallback_response(query, steps),
                steps=steps,
                success=False,
                iterations=self.config.max_iterations,
                error="Max iterations reached without a final answer.",
            )
        except Exception as exc:
            logger.exception("Unexpected exception in agent.run: %s", exc)
            return AgentResult(
                response=self._fallback_response(query, steps, error=str(exc)),
                steps=steps,
                success=False,
                iterations=len(steps) or 1,
                error=f"Service execution error: {exc}",
            )

    # ------------------------------------------------------------------
    # Core loop (asynchronous)
    # ------------------------------------------------------------------

    async def arun(self, query: str) -> AgentResult:
        """Execute the ReAct loop asynchronously with error resilience."""
        steps: list[dict] = []
        consecutive_errors = 0

        try:
            for iteration in range(1, self.config.max_iterations + 1):
                prompt = self._build_prompt(query, steps)
                try:
                    llm_response = await self._call_llm_async(prompt)
                except Exception as exc:
                    self._log(f"  Agent error during async LLM invocation: {exc}")
                    return AgentResult(
                        response=self._fallback_response(query, steps, error=str(exc)),
                        steps=steps,
                        success=False,
                        iterations=iteration,
                        error=f"LLM service error: {exc}",
                    )

                try:
                    parsed = self._parse(llm_response)
                except Exception as exc:
                    self._log(f"  Agent error parsing LLM response: {exc}")
                    parsed = {"thought": "Parsing fallback", "action": "FINAL", "params": {}, "response": llm_response}

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
                    response = parsed["response"]
                    try:
                        response = self._post_process(response, steps)
                    except Exception as exc:
                        self._log(f"  Agent post-processing error: {exc}")
                    return AgentResult(
                        response=response,
                        steps=steps,
                        success=True,
                        iterations=iteration,
                    )

                try:
                    observation = await self._execute_tool_async(parsed["action"], parsed["params"])
                except Exception as exc:
                    observation = f"ERROR: Tool execution exception: {exc}"

                steps[-1]["observation"] = observation

                if not observation or observation.startswith("ERROR:"):
                    consecutive_errors += 1
                    if consecutive_errors >= 3 and self.config.stop_after_no_action:
                        self._log(f"  Agent stopped: repeated failed tool results for '{parsed['action']}'")
                        return AgentResult(
                            response=self._fallback_response(query, steps, observation),
                            steps=steps,
                            success=False,
                            iterations=iteration,
                            error=observation,
                        )
                else:
                    consecutive_errors = 0

            return AgentResult(
                response=self._fallback_response(query, steps),
                steps=steps,
                success=False,
                iterations=self.config.max_iterations,
                error="Max iterations reached without a final answer.",
            )
        except Exception as exc:
            logger.exception("Unexpected exception in agent.arun: %s", exc)
            return AgentResult(
                response=self._fallback_response(query, steps, error=str(exc)),
                steps=steps,
                success=False,
                iterations=len(steps) or 1,
                error=f"Service execution error: {exc}",
            )

    # ------------------------------------------------------------------
    # Hook: sub-classes can override for post-processing
    # ------------------------------------------------------------------

    def _post_process(self, response: str, steps: list[dict]) -> str:
        """Override in sub-classes to refine the final response."""
        if not response:
            return response
        cleaned = response.strip()
        if "RESPONSE:" in cleaned:
            cleaned = cleaned.split("RESPONSE:", 1)[1].strip()
        return cleaned
