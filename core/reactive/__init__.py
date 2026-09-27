"""Reactive Calculation Graph (Athena/SecDB Kernel).

W96: Implements distributed in-memory reactive calculation DAG with
dirty-propagation, automatic memoization, and thread-pool work-stealing.
Inspired by Goldman Sachs SecDB and J.P. Morgan Athena architectures.
"""

from .graph import ReactiveGraph, NodeId, GraphContext
from .node import ReactiveNode, NodeStatus, ComputeFunction
from .scheduler import GraphScheduler, WorkStealingScheduler
from .memoization import MemoizationCache

__all__ = [
    "ReactiveGraph",
    "NodeId",
    "GraphContext",
    "ReactiveNode",
    "NodeStatus",
    "ComputeFunction",
    "GraphScheduler",
    "WorkStealingScheduler",
    "MemoizationCache",
]
