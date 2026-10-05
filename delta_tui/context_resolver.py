"""Phase 10 — @ context resolution (finance-aware). Resolved BEFORE model runs.

@NVDA/@AAPL symbols, @portfolio @account @risk @orders @watchlist @broker
@strategy @backtest @model @agent @mcp/* @session @dataset @scenario.
The LLM never guesses what @NVDA means.
"""
from __future__ import annotations

import re

REFS = ("portfolio", "account", "risk", "orders", "watchlist", "broker",
        "strategy", "backtest", "model", "agent", "session", "dataset", "scenario")

AT_PAT = re.compile(r"@([A-Za-z0-9_/\.-]+)")


def extract_refs(text: str) -> list[str]:
    return AT_PAT.findall(text or "")


def resolve_refs(text: str, ctx) -> dict:
    """ctx exposes: symbols (SecurityMaster), portfolio/risk/brokers dicts, mcp, sessions."""
    out: dict = {}
    for ref in extract_refs(text):
        low = ref.lower()
        if low in REFS:
            out[ref] = {"kind": low, "status": "resolved"}
        elif low.startswith("mcp/"):
            out[ref] = {"kind": "mcp", "server": low[4:], "status": "resolved"}
        elif low.startswith("@"):
            out[ref] = {"kind": "unknown", "status": "UNRESOLVED"}
        else:
            # candidate symbol -> security master (may raise Ambiguous/Unknown)
            try:
                out[ref] = {"kind": "instrument",
                            "instrument_id": ctx.symbols.resolve(ref).instrument_id,
                            "status": "resolved"}
            except Exception as e:
                out[ref] = {"kind": "instrument", "status": "UNRESOLVED",
                            "error": str(e)[:160]}
    return out


__all__ = ["REFS", "extract_refs", "resolve_refs"]
