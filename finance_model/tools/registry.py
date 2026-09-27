from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    risk: str
    handler: Callable[..., dict[str, Any]]


class FinanceToolRegistry:

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        definition: ToolDefinition,
    ) -> None:

        if definition.name in self._tools:
            raise ValueError(
                f"Tool already registered: "
                f"{definition.name}"
            )

        self._tools[definition.name] = definition

    def get(
        self,
        name: str,
    ) -> ToolDefinition:

        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(
                f"Unknown finance tool: {name}"
            )

    def names(self) -> tuple[str, ...]:
        return tuple(
            sorted(self._tools)
        )