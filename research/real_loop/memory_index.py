"""Research-memory vector + graph index (item 5).

Wraps ResearchMemory with:
- VectorIndex: deterministic token-hash embeddings (dim 256, L2-normalized),
  cosine similarity search over hypothesis+conclusion. No external deps, no
  randomness — same text always yields the same vector.
- GraphIndex: children adjacency + BFS k-hop neighborhood + shortest path +
  descendant count over parent_experiment_id links. Cycle-safe.

Both indexes rebuild deterministically from the memory payloads.
"""
from __future__ import annotations

import hashlib
import math
from collections import deque

DIM = 256


def embed(text: str, dim: int = DIM) -> tuple[float, ...]:
    """Deterministic hashing embedding: token -> dim buckets, L2-normalized."""
    vec = [0.0] * dim
    for tok in text.lower().split():
        h = int(hashlib.sha256(tok.encode()).hexdigest()[:8], 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return tuple(vec)
    return tuple(v / norm for v in vec)


def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


class VectorIndex:
    """Cosine search over experiment hypothesis+conclusion embeddings."""

    def __init__(self, dim: int = DIM) -> None:
        self.dim = dim
        self._vecs: dict[str, tuple[float, ...]] = {}

    def index(self, exp_id: str, hypothesis: str, conclusion: str = "") -> None:
        self._vecs[exp_id] = embed(f"{hypothesis} {conclusion}", self.dim)

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        q = embed(query, self.dim)
        scored = [(e, cosine(q, v)) for e, v in self._vecs.items() if any(v)]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:limit]

    def __len__(self) -> int:
        return len(self._vecs)


class GraphIndex:
    """Directed experiment graph: parent -> children + traversal."""

    def __init__(self) -> None:
        self._children: dict[str, list[str]] = {}
        self._parent: dict[str, str] = {}

    def link(self, exp_id: str, parent_id: str) -> None:
        if parent_id:
            self._children.setdefault(parent_id, []).append(exp_id)
            self._parent[exp_id] = parent_id
        self._children.setdefault(exp_id, [])

    def children(self, exp_id: str) -> list[str]:
        return list(self._children.get(exp_id, []))

    def neighborhood(self, exp_id: str, hops: int = 2) -> list[str]:
        """BFS k-hop descendants (cycle-safe)."""
        seen, out, dq = {exp_id}, [], deque([(exp_id, 0)])
        while dq:
            cur, d = dq.popleft()
            if d >= hops:
                continue
            for ch in self._children.get(cur, []):
                if ch not in seen:
                    seen.add(ch)
                    out.append(ch)
                    dq.append((ch, d + 1))
        return out

    def path(self, src: str, dst: str) -> list[str]:
        """Shortest parent->child path (BFS); [] if unreachable."""
        prev: dict[str, str] = {src: ""}
        dq = deque([src])
        while dq:
            cur = dq.popleft()
            if cur == dst:
                chain, c = [], dst
                while c:
                    chain.append(c)
                    c = prev[c]
                return chain[::-1]
            for ch in self._children.get(cur, []):
                if ch not in prev:
                    prev[ch] = cur
                    dq.append(ch)
        return []

    def descendants(self, exp_id: str) -> int:
        return len(self.neighborhood(exp_id, hops=10 ** 6))


class IndexedResearchMemory:
    """ResearchMemory + vector + graph, rebuilt from payloads on demand."""

    def __init__(self, memory) -> None:
        self.memory = memory
        self.vectors = VectorIndex()
        self.graph = GraphIndex()

    def reindex(self) -> int:
        n = 0
        for exp_id, p in self.memory._index.items():
            self.vectors.index(exp_id, p["hypothesis"], p.get("conclusion", ""))
            self.graph.link(exp_id, p.get("parent_experiment_id", ""))
            n += 1
        return n

    def record(self, *args, **kwargs) -> dict:
        out = self.memory.record(*args, **kwargs)
        exp_id = out["exp_id"]
        p = self.memory._index[exp_id]
        self.vectors.index(exp_id, p["hypothesis"], p.get("conclusion", ""))
        self.graph.link(exp_id, p.get("parent_experiment_id", ""))
        return out

    def semantic_search(self, query: str, limit: int = 10) -> list[dict]:
        hits = self.vectors.search(query, limit)
        return [{"exp_id": e, "similarity": round(s, 4),
                 "hypothesis": self.memory._index[e]["hypothesis"],
                 "stage": self.memory._index[e]["stage"]} for e, s in hits]


__all__ = ["DIM", "embed", "cosine", "VectorIndex", "GraphIndex", "IndexedResearchMemory"]
