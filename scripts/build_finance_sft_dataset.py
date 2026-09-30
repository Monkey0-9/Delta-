"""Build DELTA finance SFT dataset (Alpaca format) for Soup training.

Grounded, fail-closed examples only: every output cites evidence source,
states uncertainty, and prefers WAIT/NO_TRADE under insufficient/stale data.
Deterministic (seed 20260930). No real prices — synthetic illustrative values
labeled as such so the model learns the *reasoning shape*, never memorized numbers.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20260930
N = 640
OUT = Path(__file__).resolve().parents[1] / "data" / "finance_sft" / "delta_finance_sft.jsonl"

ASSETS = ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "JNJ", "SPY", "QQQ"]
HORIZONS = ["1D", "1W", "1M"]
ACTIONS = ["WAIT", "HOLD", "REDUCE", "INVESTIGATE", "NO_TRADE"]


def ex_analysis(rng: random.Random, i: int) -> dict:
    a = rng.choice(ASSETS)
    h = rng.choice(HORIZONS)
    conf = round(rng.uniform(0.52, 0.74), 2)
    return {
        "instruction": f"Analyze {a} for horizon {h}. Use only verified evidence; state uncertainty.",
        "input": f"Asset: {a}\nHorizon: {h}\nEvidence: illustrative synthetic snapshot #{i} (not tradeable).",
        "output": (
            f"Asset: {a}\nHorizon: {h}\nAction: WAIT\nConfidence: {conf}\n"
            f"Evidence: synthetic snapshot #{i}; no live quote verified.\n"
            f"Reason: insufficient verified evidence for a directional position.\n"
            f"Risk: a position now would carry unmeasured gap and slippage risk."
        ),
    }


def ex_risk(rng: random.Random, i: int) -> dict:
    cond = rng.choice(["stale market data", "concentration breach", "volatility spike", "model disagreement"])
    act = "NO_TRADE" if cond == "stale market data" else rng.choice(["REDUCE", "WAIT", "INVESTIGATE"])
    conf = 0.99 if act == "NO_TRADE" else round(rng.uniform(0.6, 0.8), 2)
    return {
        "instruction": "Apply DELTA pre-trade risk policy to the stated condition.",
        "input": f"Condition: {cond}\nEvidence: risk-engine snapshot #{i} (illustrative).",
        "output": (
            f"Condition: {cond}\nAction: {act}\nConfidence: {conf}\n"
            f"Evidence: risk-engine snapshot #{i}.\n"
            f"Reason: fail closed — {cond} blocks new risk until cleared.\n"
            f"Risk check: kill-switch, authorization, freshness required before any order."
        ),
    }


def ex_tool(rng: random.Random, i: int) -> dict:
    return {
        "instruction": "Select the correct DELTA tool for the request and show its output shape.",
        "input": f"Request: backtest a weekly momentum idea (case #{i}).",
        "output": (
            "Tool: backtest (event-driven simulator).\n"
            "Output: net return, gross return, costs, slippage, turnover, "
            "max drawdown, purge/embargo splits.\n"
            "Evidence: simulator run id required; never invent fill prices.\n"
            "Uncertainty: report parameter sensitivity before any conclusion."
        ),
    }


def ex_abstain(rng: random.Random, i: int) -> dict:
    q = rng.choice(["price tomorrow", "exact earnings surprise", "guaranteed return"])
    return {
        "instruction": f"What will be the {q}?",
        "input": f"Question: {q} (case #{i}).",
        "output": (
            f"I cannot answer the {q} with the evidence available.\n"
            "Evidence: no verified forecast source provided.\n"
            "Action: WAIT for data; do not trade on this question."
        ),
    }


def main() -> None:
    rng = random.Random(SEED)
    rows: list[dict] = []
    for i in range(N):
        kind = i % 4
        if kind == 0:
            rows.append(ex_analysis(rng, i))
        elif kind == 1:
            rows.append(ex_risk(rng, i))
        elif kind == 2:
            rows.append(ex_tool(rng, i))
        else:
            rows.append(ex_abstain(rng, i))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {len(rows)} examples -> {OUT}")


if __name__ == "__main__":
    main()
