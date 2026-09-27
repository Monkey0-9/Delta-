"""Reactive Calculation Graph implementation.

Athena/SecDB-inspired reactive DAG where pricing, risk, and positions
exist in a single immutable dependency graph with dirty propagation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from threading import Lock
from typing import Any, Callable
from uuid import UUID, uuid4

from .node import ReactiveNode, NodeStatus
from .scheduler import GraphScheduler


class NodeId:
    """Unique identifier for graph nodes."""
    
    def __init__(self, identifier: str | UUID) -> None:
        self._id = UUID(str(identifier)) if isinstance(identifier, str) else identifier
    
    @property
    def value(self) -> UUID:
        return self._id
    
    def __str__(self) -> str:
        return str(self._id)
    
    def __hash__(self) -> int:
        return hash(self._id)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NodeId):
            return False
        return self._id == other._id


@dataclass(frozen=True, slots=True)
class GraphContext:
    """Context passed to node compute functions."""
    graph: "ReactiveGraph"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class ReactiveGraph:
    """
    Reactive calculation graph with dirty propagation and memoization.
    
    Every pricing model, position, market tick, and risk metric is a Node
    in an in-memory, dependency-tracked graph.
    
    When a market tick invalidates a node, a topological breadth-first
    dirty-propagation pass marks child nodes dirty. Only nodes requested
    by execution or risk queries are re-evaluated (lazy evaluation).
    """
    
    def __init__(self, scheduler: GraphScheduler | None = None) -> None:
        self._nodes: dict[NodeId, ReactiveNode] = {}
        self._adjacency: dict[NodeId, set[NodeId]] = {}  # node -> dependents
        self._reverse_adjacency: dict[NodeId, set[NodeId]] = {}  # node -> dependencies
        self._lock = Lock()
        self._scheduler = scheduler or GraphScheduler()
    
    def add_node(self, node: ReactiveNode) -> None:
        """Add a node to the graph."""
        with self._lock:
            self._nodes[node.id] = node
            if node.id not in self._adjacency:
                self._adjacency[node.id] = set()
            if node.id not in self._reverse_adjacency:
                self._reverse_adjacency[node.id] = set()
    
    def add_dependency(self, dependent: NodeId, dependency: NodeId) -> None:
        """
        Add a dependency relationship: dependent depends on dependency.
        
        When dependency is invalidated, dependent will be marked dirty.
        """
        with self._lock:
            if dependent not in self._adjacency:
                self._adjacency[dependent] = set()
            if dependency not in self._reverse_adjacency:
                self._reverse_adjacency[dependency] = set()
            
            self._adjacency[dependency].add(dependent)
            self._reverse_adjacency[dependent].add(dependency)
    
    def get_node(self, node_id: NodeId) -> ReactiveNode | None:
        """Get a node by ID."""
        return self._nodes.get(node_id)
    
    def get_value(self, node_id: NodeId, context: GraphContext | None = None) -> Any:
        """
        Get the value of a node, computing if necessary.
        
        Implements lazy evaluation with automatic memoization.
        """
        if context is None:
            context = GraphContext(graph=self)
        
        node = self.get_node(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")
        
        # Check if node is dirty and needs recomputation
        if node.status == NodeStatus.DIRTY:
            self._compute_node(node, context)
        
        return node.value
    
    def invalidate(self, node_id: NodeId) -> None:
        """
        Invalidate a node and propagate dirtiness to dependents.
        
        Implements topological breadth-first dirty propagation:
        Dirty(N_k) = True ∀N_k ∈ Children(N_dirty)
        """
        with self._lock:
            self._invalidate_recursive(node_id, visited=set())
    
    def _invalidate_recursive(self, node_id: NodeId, visited: set[NodeId]) -> None:
        """Recursively invalidate node and all dependents."""
        if node_id in visited:
            return
        
        visited.add(node_id)
        
        node = self._nodes.get(node_id)
        if node:
            node.mark_dirty()
        
        # Propagate to dependents
        for dependent_id in self._adjacency.get(node_id, set()):
            self._invalidate_recursive(dependent_id, visited)
    
    def _compute_node(self, node: ReactiveNode, context: GraphContext) -> None:
        """
        Compute a node's value by evaluating its dependencies first.
        
        Implements topological evaluation order.
        """
        # Get dependency values
        dependency_values = {}
        for dep_id in self._reverse_adjacency.get(node.id, set()):
            dep_node = self._nodes.get(dep_id)
            if dep_node:
                if dep_node.status == NodeStatus.DIRTY:
                    self._compute_node(dep_node, context)
                dependency_values[dep_id] = dep_node.value
        
        # Update context with dependency values
        context_with_deps = GraphContext(
            graph=context.graph,
            timestamp=context.timestamp,
            metadata={**context.metadata, "dependencies": dependency_values}
        )
        
        # Compute node value
        try:
            value = node.compute(context_with_deps)
            node.update_value(value)
        except Exception as e:
            node.mark_error(str(e))
            raise
    
    def update_input(self, node_id: NodeId, new_value: Any) -> None:
        """
        Update an input node's value and invalidate dependents.
        
        Used for market data updates, position changes, etc.
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")
        
        node.update_value(new_value)
        self.invalidate(node_id)
    
    def get_dependents(self, node_id: NodeId) -> set[NodeId]:
        """Get all direct dependents of a node."""
        return self._adjacency.get(node_id, set()).copy()
    
    def get_dependencies(self, node_id: NodeId) -> set[NodeId]:
        """Get all direct dependencies of a node."""
        return self._reverse_adjacency.get(node_id, set()).copy()
    
    def get_all_dependents(self, node_id: NodeId) -> set[NodeId]:
        """Get all transitive dependents of a node."""
        all_dependents: set[NodeId] = set()
        frontier = self.get_dependents(node_id)
        
        while frontier:
            current = frontier.pop()
            if current not in all_dependents:
                all_dependents.add(current)
                frontier.update(self.get_dependents(current))
        
        return all_dependents
    
    def validate_acyclic(self) -> bool:
        """
        Validate that the graph is acyclic.
        
        Returns True if graph is a DAG, False if cycles detected.
        """
        visited: set[NodeId] = set()
        recursion_stack: set[NodeId] = set()
        
        def has_cycle(node_id: NodeId) -> bool:
            visited.add(node_id)
            recursion_stack.add(node_id)
            
            for dependent_id in self.get_dependents(node_id):
                if dependent_id not in visited:
                    if has_cycle(dependent_id):
                        return True
                elif dependent_id in recursion_stack:
                    return True
            
            recursion_stack.remove(node_id)
            return False
        
        for node_id in self._nodes:
            if node_id not in visited:
                if has_cycle(node_id):
                    return False
        
        return True
    
    def get_dirty_nodes(self) -> set[NodeId]:
        """Get all currently dirty nodes."""
        return {
            node_id for node_id, node in self._nodes.items()
            if node.status == NodeStatus.DIRTY
        }
    
    def clear_memoization(self) -> None:
        """Clear all memoized values and mark nodes dirty."""
        with self._lock:
            for node in self._nodes.values():
                node.mark_dirty()
    
    def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        return {
            "total_nodes": len(self._nodes),
            "dirty_nodes": len(self.get_dirty_nodes()),
            "is_acyclic": self.validate_acyclic(),
            "avg_dependencies": sum(
                len(self.get_dependencies(node_id))
                for node_id in self._nodes
            ) / len(self._nodes) if self._nodes else 0,
            "avg_dependents": sum(
                len(self.get_dependents(node_id))
                for node_id in self._nodes
            ) / len(self._nodes) if self._nodes else 0,
        }
