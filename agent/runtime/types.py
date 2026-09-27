from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class AgentTaskStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentPermission(StrEnum):
    READ_MARKET_DATA = "read_market_data"
    READ_PORTFOLIO = "read_portfolio"
    READ_RISK = "read_risk"
    RUN_ANALYSIS = "run_analysis"
    RUN_SIMULATION = "run_simulation"
    PROPOSE_TRADE = "propose_trade"
    SUBMIT_ORDER = "submit_order"
    CANCEL_ORDER = "cancel_order"
    ENABLE_AUTONOMOUS = "enable_autonomous"


@dataclass(frozen=True, slots=True)
class AgentTask:
    task_id: UUID = field(default_factory=uuid4)
    instruction: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    status: AgentTaskStatus = AgentTaskStatus.CREATED
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.instruction.strip():
            raise ValueError("Agent instruction cannot be empty.")

        timestamp = self.created_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        object.__setattr__(
            self,
            "created_at",
            timestamp.astimezone(timezone.utc),
        )


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    task_id: UUID

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Tool name cannot be empty.")


@dataclass(frozen=True, slots=True)
class ToolResult:
    success: bool
    output: Any
    tool_name: str
    task_id: UUID
    error: str | None = None