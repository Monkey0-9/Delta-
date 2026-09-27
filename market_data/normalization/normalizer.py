from __future__ import annotations

from hashlib import sha256
from typing import Iterable


class Normalizer:
    """Deterministic raw -> normalized event conversion with lineage."""

    def normalize_quote(self, raw: dict) -> dict:
        required = ("instrument_id", "bid", "ask", "event_time", "received_time", "source")
        missing = [k for k in required if k not in raw]
        if missing:
            raise ValueError(f"missing fields: {missing}")
        if float(raw["ask"]) < float(raw["bid"]):
            raise ValueError("crossed market")
        canonical = "|".join(f"{k}={raw[k]}" for k in sorted(raw))
        lineage = sha256(canonical.encode()).hexdigest()
        return {**raw, "schema_version": 1, "lineage_hash": lineage}

    def normalize_many(self, raws: Iterable[dict]) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        for raw in sorted(raws, key=lambda r: (str(r.get("received_time")), str(r.get("event_time")))):
            norm = self.normalize_quote(raw)
            if norm["lineage_hash"] in seen:
                continue  # deterministic duplicate drop
            seen.add(norm["lineage_hash"])
            out.append(norm)
        return out
