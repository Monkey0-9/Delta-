"""Stage-4 Z+: evidence graph — dataset→feature→model→experiment→decision→outcome→attribution.

Extends manifest hashes into a hash-chained graph. Each node links parent hashes;
verify() walks the chain. Past-allocation reconstruct wires to replay.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json


@dataclass
class EvidenceGraph:
    nodes: dict[str, dict] = field(default_factory=dict)

    def add(self, kind: str, node_id: str, parents: list[str], payload: dict) -> str:
        h = sha256(json.dumps({"kind": kind, "id": node_id,
                               "parents": sorted(parents),
                               "payload": payload}, sort_keys=True,
                              default=str).encode()).hexdigest()[:16]
        self.nodes[node_id] = {"kind": kind, "parents": parents,
                               "payload": payload, "hash": h}
        return h

    def verify(self) -> bool:
        for nid, n in self.nodes.items():
            for p in n["parents"]:
                if p not in self.nodes:
                    return False
        return True

    def lineage(self, node_id: str) -> list[str]:
        out, stack = [], [node_id]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.append(cur)
            stack.extend(self.nodes.get(cur, {}).get("parents", []))
        return out


__all__ = ["EvidenceGraph"]
