"""W211-W230 (I) — Quant research knowledge graph.

Dataset -> Feature -> Alpha -> Model -> Portfolio -> Experiment -> Result ->
Decision. Answers 'which previous experiments invalidated this hypothesis?'
More useful than flat RAG: traverses provenance, not just similarity.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KINDS: tuple[str, ...] = ("Dataset", "Feature", "Alpha", "Model", "Portfolio",
                          "Experiment", "Result", "Decision")


@dataclass(frozen=True, slots=True)
class KGNode:
    node_id: str
    kind: str
    label: str
    verdict: str = "unknown"  # validated|invalidated|inconclusive|unknown


class QuantKnowledgeGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, KGNode] = {}
        self.edges: dict[str, list[str]] = {}
        self.rev: dict[str, list[str]] = {}

    def add(self, node: KGNode, parents: list[str] | None = None) -> None:
        if node.kind not in KINDS:
            raise ValueError(f"bad kind {node.kind}")
        self.nodes[node.node_id] = node
        for p in parents or []:
            self.edges.setdefault(p, []).append(node.node_id)
            self.rev.setdefault(node.node_id, []).append(p)

    def invalidated_by(self, hypothesis_node: str) -> list[str]:
        """Experiments (transitively downstream) that invalidated this hypothesis."""
        out: list[str] = []
        stack, seen = [hypothesis_node], set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for c in sorted(self.edges.get(n, [])):
                nd = self.nodes[c]
                if nd.kind == "Experiment" and nd.verdict == "invalidated":
                    out.append(c)
                stack.append(c)
        return sorted(out)

    def decision_trail(self, decision_id: str) -> list[str]:
        """Full upstream provenance for a Decision node."""
        out, stack, seen = [], [decision_id], set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            out.append(n)
            stack.extend(sorted(self.rev.get(n, [])))
        return sorted(out)
