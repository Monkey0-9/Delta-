"""W116 research memory: experiment DAG on top of memory.store.

Each experiment is one hash-chained MemoryStore entry (kind="research") with:
  hypothesis, dataset/data_hashes, features/model versions, metrics
  (IC/DSR/PBO/OOS/sharpe), stage, conclusion, parent_experiment_id.

Answers "have we tested this before?" via keyword search over hypothesis +
conclusion + symbol, and traces full lineage via parent links. Failures are
first-class: stage="failed" with invalidation reason, surfaced by recall.
"""
from __future__ import annotations

import time

from memory.store import MemoryStore

MEM_VERSION = "resmem-v1"

STAGES = ("hypothesis", "running", "validated", "failed", "concluded")


class ResearchMemory:
    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or MemoryStore()
        self._index: dict[str, dict] = {}  # exp_id -> latest payload

    def record(self, exp_id: str, hypothesis: str, symbols: tuple[str, ...],
               data_hashes: dict, feature_version: str, model_version: str,
               metrics: dict, stage: str = "hypothesis", conclusion: str = "",
               parent_experiment_id: str = "") -> dict:
        if stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}.")
        if not hypothesis.strip():
            raise ValueError("hypothesis required (no hypothesis-free experiments).")
        payload = {"mem_version": MEM_VERSION, "hypothesis": hypothesis,
                   "symbols": list(symbols), "data_hashes": dict(data_hashes),
                   "feature_version": feature_version, "model_version": model_version,
                   "metrics": dict(metrics), "stage": stage, "conclusion": conclusion,
                   "parent_experiment_id": parent_experiment_id,
                   "t": time.time()}
        entry = self._store.append(exp_id, "research", payload)
        self._index[exp_id] = payload
        return {"exp_id": exp_id, "fingerprint": entry.fingerprint,
                "version": entry.version}

    def recall(self, query: str, limit: int = 10) -> list[dict]:
        """Keyword recall over hypothesis/conclusion/symbols (deterministic rank)."""
        toks = [t.lower() for t in query.split() if t]
        scored = []
        for exp_id, p in self._index.items():
            hay = f"{p['hypothesis']} {p['conclusion']} {' '.join(p['symbols'])}".lower()
            score = sum(hay.count(t) for t in toks)
            if score:
                scored.append((score, exp_id))
        scored.sort(reverse=True)
        return [{"exp_id": e, "score": s,
                 "hypothesis": self._index[e]["hypothesis"],
                 "stage": self._index[e]["stage"],
                 "conclusion": self._index[e]["conclusion"]} for s, e in scored[:limit]]

    def lineage(self, exp_id: str) -> list[dict]:
        """Parent chain root-first; breaks loudly on missing links."""
        chain = []
        cur = exp_id
        seen = set()
        while cur:
            if cur in seen:
                raise ValueError(f"lineage cycle at {cur}.")
            seen.add(cur)
            p = self._index.get(cur)
            if p is None:
                raise ValueError(f"unknown experiment in lineage: {cur}.")
            chain.append({"exp_id": cur, "stage": p["stage"],
                          "hypothesis": p["hypothesis"]})
            cur = p["parent_experiment_id"]
        return chain[::-1]

    def failures(self, limit: int = 20) -> list[dict]:
        out = [{"exp_id": e, "hypothesis": p["hypothesis"],
                "conclusion": p["conclusion"]}
               for e, p in self._index.items() if p["stage"] == "failed"]
        return out[:limit]

    def verify(self, exp_id: str) -> bool:
        return all(e.verify() for e in self._store.history(exp_id))


__all__ = ["MEM_VERSION", "STAGES", "ResearchMemory"]
