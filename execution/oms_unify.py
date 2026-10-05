"""G28/G29/G30 — OMS unify (persistent idempotency) + agent loop + prod gates (thin slice)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


class IdempotencyStore:
    def __init__(self, db: str = "data/idempotency.sqlite") -> None:
        self.db = Path(db)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.db))
        try:
            con.execute("CREATE TABLE IF NOT EXISTS seen(client_id TEXT PRIMARY KEY, order_id TEXT)")
        finally:
            con.close()

    def claim(self, client_id: str, order_id: str) -> bool:
        con = sqlite3.connect(str(self.db))
        try:
            try:
                con.execute("INSERT INTO seen VALUES (?,?)", (client_id, order_id))
                con.commit()
                return True
            except sqlite3.IntegrityError:
                return False
        finally:
            con.close()


@dataclass
class ResearchTask:
    hyp: str
    budget: float = 1.0


def next_hypothesis(failures: list[str]) -> str:
    if any("liquidity" in f for f in failures):
        return "liquidity-regime conditioned alpha"
    if any("cost" in f for f in failures):
        return "cost-aware sizing"
    return "baseline momentum"


R_GATES = ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]


def certify(gates: dict[str, bool]) -> str:
    for g in R_GATES:
        if not gates.get(g, False):
            return g
    return "R10"
