"""
Research Memory with Graph and Vector Index for DELTA OS.

This module implements comprehensive research memory with:
- Vector similarity search for experiments
- Graph database for relationships
- Complete experiment provenance
- Semantic experiment retrieval
- Feature lineage tracking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Any, Set, Tuple
from uuid import UUID, uuid4
import hashlib
import json
import numpy as np
from collections import defaultdict
from pathlib import Path


class MemoryType(Enum):
    """Type of memory item."""
    EXPERIMENT = "experiment"
    MODEL = "model"
    DATASET = "dataset"
    FEATURE = "feature"
    SIGNAL = "signal"


@dataclass
class VectorEmbedding:
    """
    Vector embedding for similarity search.
    
    Attributes:
        embedding_id: Unique embedding identifier
        vector: Vector representation
        memory_type: Type of memory item
        memory_id: ID of the memory item
        timestamp: Embedding timestamp
        metadata: Additional metadata
    """
    embedding_id: str
    vector: np.ndarray
    memory_type: MemoryType
    memory_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def dimension(self) -> int:
        """Vector dimension."""
        return len(self.vector)


@dataclass
class GraphNode:
    """
    Graph node for relationship tracking.
    
    Attributes:
        node_id: Unique node identifier
        node_type: Type of node
        attributes: Node attributes
        edges: List of connected node IDs
        timestamp: Node creation timestamp
    """
    node_id: str
    node_type: MemoryType
    attributes: Dict[str, Any] = field(default_factory=dict)
    edges: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExperimentProvenance:
    """
    Complete experiment provenance for reproducibility.
    
    Attributes:
        experiment_id: Experiment identifier
        dataset_version: Dataset version used
        model_version: Model version used
        feature_version: Feature version used
        parameter_version: Parameter version
        random_seed: Random seed used
        code_commit: Git commit hash
        environment: Environment details
        results: Experiment results
        metrics: Performance metrics
        timestamp: Experiment timestamp
    """
    experiment_id: str
    dataset_version: str
    model_version: str
    feature_version: str
    parameter_version: str
    random_seed: int
    code_commit: str
    environment: Dict[str, Any]
    results: Dict[str, Any]
    metrics: Dict[str, float]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def fingerprint(self) -> str:
        """Generate unique fingerprint for reproducibility."""
        payload = {
            'dataset_version': self.dataset_version,
            'model_version': self.model_version,
            'feature_version': self.feature_version,
            'parameter_version': self.parameter_version,
            'random_seed': self.random_seed,
            'code_commit': self.code_commit,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()


class VectorIndex:
    """
    Vector similarity search index.
    
    Features:
    - Vector similarity search
    - Cosine similarity
    - Euclidean distance
    - Fast nearest neighbor search
    """
    
    def __init__(self, dimension: int = 128):
        """
        Initialize vector index.
        
        Args:
            dimension: Vector dimension
        """
        self._dimension = dimension
        self._embeddings: Dict[str, VectorEmbedding] = {}
        self._index_structure: List[str] = []  # Simple list for now
    
    def add_embedding(
        self,
        vector: np.ndarray,
        memory_type: MemoryType,
        memory_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add vector embedding to index.
        
        Args:
            vector: Vector to index
            memory_type: Type of memory item
            memory_id: ID of memory item
            metadata: Additional metadata
            
        Returns:
            Embedding ID
        """
        embedding_id = str(uuid4())
        
        embedding = VectorEmbedding(
            embedding_id=embedding_id,
            vector=vector,
            memory_type=memory_type,
            memory_id=memory_id,
            metadata=metadata or {}
        )
        
        self._embeddings[embedding_id] = embedding
        self._index_structure.append(embedding_id)
        
        return embedding_id
    
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        memory_type: Optional[MemoryType] = None
    ) -> List[Tuple[str, float]]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query vector
            top_k: Number of results to return
            memory_type: Filter by memory type
            
        Returns:
            List of (embedding_id, similarity_score)
        """
        similarities = []
        
        for embedding_id, embedding in self._embeddings.items():
            # Filter by memory type if specified
            if memory_type and embedding.memory_type != memory_type:
                continue
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_vector, embedding.vector)
            similarities.append((embedding_id, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


class GraphDatabase:
    """
    Graph database for relationship tracking.
    
    Features:
    - Experiment relationships
    - Feature lineage
    - Model dependencies
    - Dataset relationships
    """
    
    def __init__(self):
        """Initialize graph database."""
        self._nodes: Dict[str, GraphNode] = {}
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)
    
    def add_node(
        self,
        node_id: str,
        node_type: MemoryType,
        attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add node to graph.
        
        Args:
            node_id: Node identifier
            node_type: Type of node
            attributes: Node attributes
        """
        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            attributes=attributes or {}
        )
        self._nodes[node_id] = node
    
    def add_edge(self, from_node: str, to_node: str, edge_type: str = "related") -> None:
        """
        Add edge between nodes.
        
        Args:
            from_node: Source node
            to_node: Target node
            edge_type: Type of edge
        """
        if from_node not in self._nodes:
            self.add_node(from_node, MemoryType.EXPERIMENT)
        
        if to_node not in self._nodes:
            self.add_node(to_node, MemoryType.EXPERIMENT)
        
        self._nodes[from_node].edges.append(to_node)
        self._adjacency[from_node].add(to_node)
    
    def get_neighbors(self, node_id: str) -> List[str]:
        """
        Get neighbors of a node.
        
        Args:
            node_id: Node identifier
            
        Returns:
            List of neighbor node IDs
        """
        return list(self._adjacency.get(node_id, set()))
    
    def get_shortest_path(
        self,
        from_node: str,
        to_node: str
    ) -> List[str]:
        """
        Get shortest path between nodes (BFS).
        
        Args:
            from_node: Source node
            to_node: Target node
            
        Returns:
            List of node IDs in path
        """
        if from_node not in self._nodes or to_node not in self._nodes:
            return []
        
        if from_node == to_node:
            return [from_node]
        
        # BFS
        queue = [from_node]
        visited = {from_node}
        parent = {from_node: None}
        
        while queue:
            current = queue.pop(0)
            
            if current == to_node:
                # Reconstruct path
                path = []
                while current is not None:
                    path.append(current)
                    current = parent[current]
                return path[::-1]
            
            for neighbor in self.get_neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = current
                    queue.append(neighbor)
        
        return []


class ResearchMemory:
    """
    Research memory with vector and graph index.
    
    Features:
    - Vector similarity search
    - Graph relationship tracking
    - Complete provenance
    - Semantic retrieval
    - Reproducibility bundles
    """
    
    def __init__(self, vector_dimension: int = 128):
        """
        Initialize research memory.
        
        Args:
            vector_dimension: Dimension for vector embeddings
        """
        self._vector_index = VectorIndex(vector_dimension)
        self._graph_db = GraphDatabase()
        self._provenance: Dict[str, ExperimentProvenance] = {}
        
        # Storage paths
        self._storage_path = Path("research/memory/storage")
        self._storage_path.mkdir(parents=True, exist_ok=True)
    
    def add_experiment(
        self,
        experiment_id: str,
        features: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add experiment to research memory.
        
        Args:
            experiment_id: Experiment identifier
            features: Experiment features
            metadata: Additional metadata
            
        Returns:
            Embedding ID
        """
        # Create vector embedding from features
        feature_values = np.array(list(features.values()))
        # Pad or truncate to desired dimension
        if len(feature_values) < self._vector_index._dimension:
            feature_values = np.pad(feature_values, (0, self._vector_index._dimension - len(feature_values)))
        else:
            feature_values = feature_values[:self._vector_index._dimension]
        
        # Add to vector index
        embedding_id = self._vector_index.add_embedding(
            vector=feature_values,
            memory_type=MemoryType.EXPERIMENT,
            memory_id=experiment_id,
            metadata=metadata
        )
        
        # Add to graph
        self._graph_db.add_node(experiment_id, MemoryType.EXPERIMENT, metadata)
        
        return embedding_id
    
    def add_relationship(
        self,
        from_experiment: str,
        to_experiment: str,
        relationship_type: str = "derived_from"
    ) -> None:
        """
        Add relationship between experiments.
        
        Args:
            from_experiment: Source experiment
            to_experiment: Target experiment
            relationship_type: Type of relationship
        """
        self._graph_db.add_edge(from_experiment, to_experiment, relationship_type)
    
    def add_provenance(self, provenance: ExperimentProvenance) -> None:
        """
        Add experiment provenance.
        
        Args:
            provenance: Experiment provenance
        """
        self._provenance[provenance.experiment_id] = provenance
        
        # Add to graph as well
        self._graph_db.add_node(
            provenance.experiment_id,
            MemoryType.EXPERIMENT,
            {'fingerprint': provenance.fingerprint()}
        )
    
    def search_similar_experiments(
        self,
        features: Dict[str, float],
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Search for similar experiments.
        
        Args:
            features: Query features
            top_k: Number of results
            
        Returns:
            List of (experiment_id, similarity_score)
        """
        # Create query vector
        feature_values = np.array(list(features.values()))
        if len(feature_values) < self._vector_index._dimension:
            feature_values = np.pad(feature_values, (0, self._vector_index._dimension - len(feature_values)))
        else:
            feature_values = feature_values[:self._vector_index._dimension]
        
        # Search vector index
        results = self._vector_index.search(feature_values, top_k, MemoryType.EXPERIMENT)
        
        return results
    
    def get_experiment_lineage(self, experiment_id: str) -> List[str]:
        """
        Get experiment lineage (ancestors).
        
        Args:
            experiment_id: Experiment identifier
            
        Returns:
            List of ancestor experiment IDs
        """
        lineage = []
        
        # Find all nodes that point to this experiment
        for node_id, node in self._graph_db._nodes.items():
            if experiment_id in node.edges:
                lineage.append(node_id)
        
        return lineage
    
    def get_reproducibility_bundle(self, experiment_id: str) -> Dict[str, Any]:
        """
        Get reproducibility bundle for experiment.
        
        Args:
            experiment_id: Experiment identifier
            
        Returns:
            Reproducibility bundle
        """
        provenance = self._provenance.get(experiment_id)
        
        if provenance is None:
            return {}
        
        return {
            'experiment_id': provenance.experiment_id,
            'fingerprint': provenance.fingerprint(),
            'dataset_version': provenance.dataset_version,
            'model_version': provenance.model_version,
            'feature_version': provenance.feature_version,
            'parameter_version': provenance.parameter_version,
            'random_seed': provenance.random_seed,
            'code_commit': provenance.code_commit,
            'environment': provenance.environment,
            'results': provenance.results,
            'metrics': provenance.metrics,
            'timestamp': provenance.timestamp.isoformat(),
        }


__all__ = [
    "MemoryType",
    "VectorEmbedding",
    "GraphNode",
    "ExperimentProvenance",
    "VectorIndex",
    "GraphDatabase",
    "ResearchMemory",
]
