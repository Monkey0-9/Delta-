"""Research agent module for DELTA OS.

NOTE: research.agent.autonomous_agent (random-Sharpe synthetic research)
was DELETED in P0 (false-intelligence purge). Importing it raises
ImportError by design — use research.real_loop.research_agent or the
canonical ai/ runtime instead.
"""

from research.agent.tool_registry import ToolRegistry, ToolDefinition
from research.agent.permissions import PermissionManager, PermissionError
from research.agent.research_loop import ResearchLoop, ProvenanceEntry

__all__ = [
    "ToolRegistry",
    "ToolDefinition",
    "PermissionManager",
    "PermissionError",
    "ResearchLoop",
    "ProvenanceEntry",
]
