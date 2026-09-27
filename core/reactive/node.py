"""Reactive Node implementation for the calculation graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from threading import Lock
from typing import Any, Callable
from uuid import UUID, uuid4

from .graph import GraphContext


class NodeStatus(StrEnum):
    """Status of a reactive node."""
    CLEAN = "clean"
    DIRTY = "dirty"
    COMPUTING = "computing"
    ERROR = "error"


ComputeFunction = Callable[[GraphContext], Any]


@dataclass(frozen=True, slots=True)
class ReactiveNode:
    """
    Reactive node in the calculation graph.
    
    Computes V_i = f_i(V_{parents(i)}) when dirty.
    Supports automatic memoization and dirty propagation.
    """
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    compute_fn: ComputeFunction = lambda ctx: None
    
    # Node state
    value: Any = None
    status: NodeStatus = NodeStatus.DIRTY
    error_message: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    computed_at: datetime | None = None
    compute_count: int = 0
    
    # Thread-safe state management
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    
    def mark_dirty(self) -> None:
        """Mark node as dirty, requiring recomputation."""
        with self._lock:
            self._set_status(NodeStatus.DIRTY)
    
    def mark_computing(self) -> None:
        """Mark node as currently being computed."""
        with self._lock:
            self._set_status(NodeStatus.COMPUTING)
    
    def mark_error(self, error_message: str) -> None:
        """Mark node as having encountered an error."""
        with self._lock:
            self._set_status(NodeStatus.ERROR)
            object.__setattr__(self, "error_message", error_message)
    
    def update_value(self, new_value: Any) -> None:
        """Update node's computed value and mark as clean."""
        with self._lock:
            object.__setattr__(self, "value", new_value)
            object.__setattr__(self, "computed_at", datetime.now(timezone.utc))
            object.__setattr__(self, "compute_count", self.compute_count + 1)
            object.__setattr__(self, "error_message", "")
            self._set_status(NodeStatus.CLEAN)
    
    def _set_status(self, status: NodeStatus) -> None:
        """Internal method to set status (not thread-safe, must hold lock)."""
        object.__setattr__(self, "status", status)
    
    def compute(self, context: GraphContext) -> Any:
        """
        Compute the node's value using its compute function.
        
        This method is called by the graph scheduler when the node
        needs to be evaluated.
        """
        self.mark_computing()
        
        try:
            result = self.compute_fn(context)
            self.update_value(result)
            return result
        except Exception as e:
            self.mark_error(str(e))
            raise
    
    def is_dirty(self) -> bool:
        """Check if node is dirty."""
        return self.status == NodeStatus.DIRTY
    
    def is_clean(self) -> bool:
        """Check if node is clean (computed and up-to-date)."""
        return self.status == NodeStatus.CLEAN
    
    def is_error(self) -> bool:
        """Check if node is in error state."""
        return self.status == NodeStatus.ERROR
    
    def get_age_ms(self) -> float:
        """Get age of computed value in milliseconds."""
        if self.computed_at is None:
            return float('inf')
        
        age = datetime.now(timezone.utc) - self.computed_at
        return age.total_seconds() * 1000
    
    def __repr__(self) -> str:
        return (
            f"ReactiveNode(id={self.id}, name={self.name}, "
            f"status={self.status}, value={self.value})"
        )
