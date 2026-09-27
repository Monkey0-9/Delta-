from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agent.runtime.types import (
    AgentPermission,
    ToolCall,
    ToolResult,
)


ToolFunction = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    function: ToolFunction
    permissions: frozenset[AgentPermission]


class ToolRegistry:
    """
    Explicit allow-listed tool registry.

    The agent cannot execute arbitrary Python functions.
    Every callable must be explicitly registered.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        function: ToolFunction,
        permissions: frozenset[AgentPermission] = frozenset(),
    ) -> None:
        normalized = name.strip()

        if not normalized:
            raise ValueError("Tool name cannot be empty.")

        if normalized in self._tools:
            raise ValueError(f"Tool already registered: {normalized}")

        self._tools[normalized] = ToolDefinition(
            name=normalized,
            description=description,
            function=function,
            permissions=permissions,
        )

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def list(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())

    def execute(
        self,
        call: ToolCall,
        granted_permissions: frozenset[AgentPermission],
    ) -> ToolResult:
        definition = self.get(call.name)

        missing = definition.permissions - granted_permissions

        if missing:
            return ToolResult(
                success=False,
                output=None,
                tool_name=call.name,
                task_id=call.task_id,
                error=(
                    "Permission denied: "
                    + ", ".join(sorted(permission.value for permission in missing))
                ),
            )

        try:
            result = definition.function(**call.arguments)

            return ToolResult(
                success=True,
                output=result,
                tool_name=call.name,
                task_id=call.task_id,
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                output=None,
                tool_name=call.name,
                task_id=call.task_id,
                error=f"{type(exc).__name__}: {exc}",
            )