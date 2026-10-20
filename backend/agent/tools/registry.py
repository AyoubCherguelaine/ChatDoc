"""
Base Tool dataclass and ToolRegistry.

A :class:`Tool` wraps a plain Python callable with a name, description,
and JSON-style parameter schema.  The :class:`ToolRegistry` manages the
collection of available tools and dispatches calls.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Tool:
    """
    A callable tool the agent can invoke.

    Attributes
    ----------
    name
        The function name used in ACTION lines.
    description
        Human-readable description shown in the prompt.
    parameters
        JSON-schema-style dict describing the parameters.
    func
        The synchronous callable.
    async_func
        Optional async callable (falls back to ``func`` if absent).
    timeout
        Optional timeout in seconds (for future use).
    """

    name: str
    description: str
    parameters: dict
    func: Callable[..., Any]
    async_func: Optional[Callable[..., Any]] = None
    timeout: Optional[int] = None

    @property
    def schema_json(self) -> str:
        """JSON string of the parameter schema for prompt injection."""
        return json.dumps(self.parameters, indent=2)

    def __call__(self, **kwargs: Any) -> str:
        try:
            return str(self.func(**kwargs))
        except Exception as exc:
            return f"ERROR: {exc}"

    async def acall(self, **kwargs: Any) -> str:
        if self.async_func is not None:
            try:
                return str(await self.async_func(**kwargs))
            except Exception as exc:
                return f"ERROR: {exc}"
        return self(**kwargs)

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
    ) -> "Tool":
        """
        Auto-create a Tool from a function's docstring and signature.
        """
        name = name or func.__name__
        description = description or inspect.getdoc(func) or func.__name__

        if parameters is None:
            sig = inspect.signature(func)
            params: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
            for pname, param in sig.parameters.items():
                ptype = param.annotation if param.annotation != inspect.Parameter.empty else str
                ptype_str = _to_json_type(ptype)
                params["properties"][pname] = {
                    "type": ptype_str,
                    "description": "",
                }
                if param.default == inspect.Parameter.empty and pname not in (
                    "self",
                    "kwargs",
                ):
                    params["required"].append(pname)

            parameters = params

        return cls(
            name=name,
            description=description,
            parameters=parameters,
            func=func,
        )


def _to_json_type(tp: type) -> str:
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    return mapping.get(tp, "string")


class ToolRegistry:
    """Holds and dispatches tools for the agent."""

    def __init__(self, tools: Optional[list[Tool]] = None):
        self._tools: dict[str, Tool] = {}
        if tools:
            for t in tools:
                self.register(t)

    def register(self, tool: Tool) -> "ToolRegistry":
        self._tools[tool.name] = tool
        return self

    def unregister(self, name: str) -> "ToolRegistry":
        self._tools.pop(name, None)
        return self

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    @property
    def tools(self) -> list[Tool]:
        return list(self._tools.values())

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def format_tool_descriptions(self) -> str:
        """Format tools as prompt text for the LLM."""
        lines = []
        for t in self.tools:
            lines.append(f"Tool: {t.name}")
            lines.append(f"  Description: {t.description}")
            lines.append(f"  Parameters: {t.schema_json}")
            lines.append("")
        return "\n".join(lines)

    def execute(self, name: str, params: dict[str, Any]) -> str:
        """Execute a tool by name with parameters. Returns string result."""
        tool = self.get(name)
        if tool is None:
            return f"ERROR: Unknown tool '{name}'. Available: {self.tool_names}"
        return tool(**params)

    async def aexecute(self, name: str, params: dict[str, Any]) -> str:
        tool = self.get(name)
        if tool is None:
            return f"ERROR: Unknown tool '{name}'. Available: {self.tool_names}"
        return await tool.acall(**params)
