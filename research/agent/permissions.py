"""
Role-based tool permissions for research automation in DELTA OS.

Maps roles to the tools they may invoke. Simple allow-list model
with no network or LLM dependencies.
"""

from __future__ import annotations

from typing import Dict, List, Set


class PermissionError(Exception):
    """Raised when a role attempts an unauthorized tool."""


class PermissionManager:
    """
    Allow-list permission manager mapping roles to tools.

    Features:
    - Grant tool access to a role
    - Revoke tool access
    - Check role/tool authorization
    - Enforce with exception on denial
    """

    def __init__(self) -> None:
        """Initialize empty permission map."""
        self._grants: Dict[str, Set[str]] = {}

    def grant(self, tool: str, role: str) -> None:
        """
        Grant a role access to a tool.

        Args:
            tool: Tool identifier
            role: Role identifier

        Raises:
            ValueError: If tool or role is empty.
        """
        if not tool or not isinstance(tool, str):
            raise ValueError("Tool must be a non-empty string")
        if not role or not isinstance(role, str):
            raise ValueError("Role must be a non-empty string")
        self._grants.setdefault(role, set()).add(tool)

    def revoke(self, tool: str, role: str) -> bool:
        """
        Revoke a role's access to a tool.

        Args:
            tool: Tool identifier
            role: Role identifier

        Returns:
            True if a grant was removed, False otherwise.
        """
        tools = self._grants.get(role)
        if not tools or tool not in tools:
            return False
        tools.discard(tool)
        if not tools:
            del self._grants[role]
        return True

    def check(self, role: str, tool: str) -> bool:
        """
        Check whether a role may invoke a tool.

        Args:
            role: Role identifier
            tool: Tool identifier

        Returns:
            True if granted, False otherwise.
        """
        return tool in self._grants.get(role, set())

    def enforce(self, role: str, tool: str) -> None:
        """
        Enforce authorization, raising on denial.

        Args:
            role: Role identifier
            tool: Tool identifier

        Raises:
            PermissionError: If role lacks access to tool.
        """
        if not self.check(role, tool):
            raise PermissionError(
                f"Role '{role}' is not authorized for tool '{tool}'"
            )

    def tools_for(self, role: str) -> List[str]:
        """
        List tools granted to a role.

        Args:
            role: Role identifier

        Returns:
            Sorted list of tool identifiers.
        """
        return sorted(self._grants.get(role, set()))

    def roles_for(self, tool: str) -> List[str]:
        """
        List roles granted access to a tool.

        Args:
            tool: Tool identifier

        Returns:
            Sorted list of role identifiers.
        """
        return sorted(
            role for role, tools in self._grants.items() if tool in tools
        )


__all__ = [
    "PermissionError",
    "PermissionManager",
]
