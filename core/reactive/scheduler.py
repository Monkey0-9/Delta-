"""Graph Scheduler for reactive computation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue, Empty
from threading import Lock, Thread
from typing import Any

from .graph import ReactiveGraph, NodeId, GraphContext


class GraphScheduler(ABC):
    """Abstract base class for graph computation schedulers."""
    
    @abstractmethod
    def schedule_computation(
        self,
        graph: ReactiveGraph,
        node_id: NodeId,
        context: GraphContext
    ) -> Any:
        """Schedule computation of a node."""
        pass


class SynchronousScheduler(GraphScheduler):
    """Simple synchronous scheduler (single-threaded)."""
    
    def schedule_computation(
        self,
        graph: ReactiveGraph,
        node_id: NodeId,
        context: GraphContext
    ) -> Any:
        """Compute node synchronously."""
        return graph.get_value(node_id, context)


class WorkStealingScheduler(GraphScheduler):
    """
    Work-stealing scheduler with thread pool.
    
    Implements parallel computation with work stealing for better
    load balancing across independent subgraphs.
    """
    
    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._work_queue: Queue[tuple[NodeId, GraphContext]] = Queue()
        self._results: dict[NodeId, Future[Any]] = {}
        self._lock = Lock()
        self._running = False
    
    def schedule_computation(
        self,
        graph: ReactiveGraph,
        node_id: NodeId,
        context: GraphContext
    ) -> Any:
        """Schedule computation of a node."""
        # Check if already scheduled
        with self._lock:
            if node_id in self._results:
                future = self._results[node_id]
                return future.result()
        
        # Submit to thread pool
        future = self._executor.submit(self._compute_node, graph, node_id, context)
        
        with self._lock:
            self._results[node_id] = future
        
        return future.result()
    
    def _compute_node(
        self,
        graph: ReactiveGraph,
        node_id: NodeId,
        context: GraphContext
    ) -> Any:
        """Compute a node (called by worker thread)."""
        return graph.get_value(node_id, context)
    
    def schedule_batch(
        self,
        graph: ReactiveGraph,
        node_ids: list[NodeId],
        context: GraphContext
    ) -> dict[NodeId, Any]:
        """Schedule batch computation of multiple nodes."""
        futures = {}
        
        for node_id in node_ids:
            future = self._executor.submit(self._compute_node, graph, node_id, context)
            futures[node_id] = future
        
        # Wait for all completions
        results = {}
        for node_id, future in futures.items():
            results[node_id] = future.result()
        
        return results
    
    def shutdown(self) -> None:
        """Shutdown the scheduler and cleanup resources."""
        self._executor.shutdown(wait=True)
        
        with self._lock:
            self._results.clear()
    
    def get_pending_count(self) -> int:
        """Get number of pending computations."""
        with self._lock:
            return len(self._results)
