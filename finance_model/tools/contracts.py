from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ToolRisk(StrEnum):
    READ_ONLY = "read_only"
    SIMULATION = "simulation"
    SENSITIVE = "sensitive"


@dataclass(frozen=True, slots=True)
class ToolRequest:
    tool_name: str
    arguments: dict[str, Any]
    request_id: str


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_name: str
    request_id: str
    success: bool
    data: dict[str, Any]
    error: str | None = None