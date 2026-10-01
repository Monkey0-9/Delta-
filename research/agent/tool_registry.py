"""
Tool registry for research automation in DELTA OS.

Provides a lightweight named-function registry used by the
autonomous research loop: register, lookup, list, and invoke.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class ToolDefinition:
    """
    Named tool entry.

    Attributes:
        name: Tool identifier
        fn: Callable implementing the tool
        description: Human-readable description
        metadata: Additional metadata
    """
    name: str
    fn: Callable[..., Any]
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Named callable registry for research tools.

    Features:
    - Register named callables
    - Lookup by name
    - Sorted tool listing
    - Direct invocation
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        fn: Callable[..., Any],
        description: str = "",
        metadata: Dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> None:
        """
        Register a tool callable.

        Args:
            name: Tool identifier
            fn: Callable implementing the tool
            description: Human-readable description
            metadata: Additional metadata
            overwrite: Allow replacing an existing entry. Default False:
                replacement is a governed operation — pass overwrite=True
                explicitly (audited call sites only).

        Raises:
            ValueError: If name invalid, fn not callable, or duplicate
                when overwrite is False.
        """
        if not name or not isinstance(name, str):
            raise ValueError("Tool name must be a non-empty string")
        if not callable(fn):
            raise ValueError(f"Tool '{name}' fn must be callable")
        if name in self._tools and not overwrite:
            raise ValueError(f"Tool '{name}' already registered")
        self._tools[name] = ToolDefinition(
            name=name,
            fn=fn,
            description=description,
            metadata=dict(metadata or {}),
        )

    def get(self, name: str) -> Callable[..., Any]:
        """
        Get a tool callable by name.

        Args:
            name: Tool identifier

        Returns:
            Registered callable

        Raises:
            KeyError: If tool is not registered.
        """
        try:
            return self._tools[name].fn
        except KeyError:
            raise KeyError(f"Tool '{name}' not found") from None

    def has(self, name: str) -> bool:
        """
        Check whether a tool is registered.

        Args:
            name: Tool identifier

        Returns:
            True if registered, False otherwise.
        """
        return name in self._tools

    def list_tools(self) -> List[str]:
        """
        List registered tool names.

        Returns:
            Sorted list of tool names.
        """
        return sorted(self._tools.keys())

    def describe(self, name: str) -> ToolDefinition:
        """
        Get full tool definition.

        Args:
            name: Tool identifier

        Returns:
            ToolDefinition entry

        Raises:
            KeyError: If tool is not registered.
        """
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Tool '{name}' not found") from None

    def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Invoke a registered tool.

        Args:
            name: Tool identifier
            *args: Positional tool arguments
            **kwargs: Keyword tool arguments

        Returns:
            Tool result

        Raises:
            KeyError: If tool is not registered.
        """
        return self.get(name)(*args, **kwargs)

    def unregister(self, name: str) -> bool:
        """
        Remove a tool registration.

        Args:
            name: Tool identifier

        Returns:
            True if removed, False if absent.
        """
        return self._tools.pop(name, None) is not None


__all__ = [
    "ToolDefinition",
    "ToolRegistry",
]
