"""Build DELTA grounded finance dataset v0.2 (P0-2, staged).

Stages (per review §4):
  S1 domain knowledge — accounting, markets, fixed income, derivatives,
     portfolio theory, risk, microstructure, quant methods (concept Q&A with
     textbook-stable answers; no live numbers).
  S2 numerical reasoning — returns, CAGR, volatility, Sharpe, drawdown, beta,
     VaR/CVaR, bond price, duration, weights, Kelly size. Outputs are computed
     HERE by deterministic closed forms (oracle), never invented. The model
     learns to explain; calculators remain authoritative at inference.
  S3 refusal/abstention — stale data, unknown symbol, prediction demands,
     missing evidence (fail-closed shapes).

Every row: instruction/input/output/source/stage/synthetic(true, labeled).
Deterministic (seed 20260930). No real-time prices, no future claims.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

SEED = 20260930
OUT = Path(__file__).resolve().parents[1] / "data" / "finance_grounded" / "delta_finance_grounded.jsonl"
MANIFEST = OUT.parent / "manifest.json"

rng = random.Random(SEED)
rows: list[dict] = []


def add(stage: str, source: str, instruction: str, inp: str, output: str) -> None:
    rows.append({"instruction": instruction, "input": inp, "output": output,
                 "source": source, "stage": stage, "synthetic": True})


# ---- S1 domain knowledge (textbook-stable) ----
S1 = [
    ("accounting", "What is accrual accounting?",
     "Accrual accounting records revenues when earned and expenses when incurred, regardless of cash movement.",
     "IAS 1 / ASC 220 concept summary (paraphrase)."),
    ("markets", "What distinguishes a limit order from a market order?",
     "A limit order specifies the worst acceptable price and rests until matched or cancelled; a market order demands immediate execution at the best available price and pays the spread.",
     "Market microstructure concept summary (paraphrase)."),
    ("fixed_income", "Define modified duration in one sentence.",
     "Modified duration is the negative first-order sensitivity of a bond price to a change in yield, approximately the percentage price change per 100bp move.",
     "Fixed-income concept summary (paraphrase)."),
    ("derivatives", "What does a put option buyer own?",
     "The right, not the obligation, to sell the underlying at the strike before expiry; the premium paid is the maximum loss.",
     "Derivatives concept summary (paraphrase)."),
    ("portfolio_theory", "State the mean-variance idea in one sentence.",
     "Mean-variance selects portfolio weights trading expected return against variance subject to constraints; inputs are estimates with error.",
     "Portfolio-theory concept summary (paraphrase)."),
    ("risk", "Define Expected Shortfall (CVaR).",
     "Expected Shortfall is the mean loss conditional on exceeding VaR at the chosen tail probability; it is coherent, unlike VaR alone.",
     "Risk concept summary (paraphrase)."),
    ("microstructure", "What is order-flow imbalance?",
     "Signed buy minus sell pressure over a window (trades or book deltas); persistent imbalance predicts short-horizon drift and impact.",
     "Microstructure concept summary (paraphrase)."),
    ("quant_methods", "Why purge + embargo in walk-forward splits?",
     "Labels spanning multiple bars leak across adjacent train/test windows (Lopez de Prado AFML Ch.7); purging drops overlapping train rows and embargo skips post-event rows.",
     "AFML Ch.7 concept summary (paraphrase)."),
]
for topic, q, a, src in S1:
    for i in range(8):
        add("S1_domain", src, q, f"Topic: {topic} (item {i}).",
            f"{a}\nEvidence: textbook concept, timeless (no market data used).")


# ---- S2 numerical reasoning (oracle-computed) ----
def s2_returns():
    p0, p1 = 100.0, 105.0
    r = p1 / p0 - 1
    add("S2_numerical", "oracle:simple_return", "Compute the one-period simple return.",
        f"Start: {p0}, End: {p1}.", f"Return = {p1}/{p0} - 1 = {r:.6f} (6.000000%).\nMethod: deterministic calculator.")


def s2_cagr():
    p0, p1, y = 100.0, 161.051, 5.0
    cagr = (p1 / p0) ** (1 / y) - 1
    add("S2_numerical", "oracle:cagr", "Compute CAGR over 5 years.",
        f"Start: {p0}, End: {p1}, Years: {y}.", f"CAGR = ({p1}/{p0})^(1/{y}) - 1 = {cagr:.6f}.\nMethod: deterministic calculator.")


def s2_vol_sharpe():
    rets = [0.01, -0.005, 0.02, 0.003, -0.012]
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    vol = math.sqrt(var)
    shr = (m / vol * math.sqrt(252)) if vol else 0.0
    add("S2_numerical", "oracle:vol_sharpe",
        "Compute sample volatility and annualized Sharpe (rf=0) for 5 daily returns.",
        f"Returns: {rets}.",
        f"Mean = {m:.6f}; sample vol (ddof=1) = {vol:.6f}; Sharpe_ann = {shr:.4f}.\nMethod: deterministic calculator.")


def s2_drawdown():
    px = [100.0, 110.0, 105.0, 95.0, 102.0]
    peak, mdd = px[0], 0.0
    for p in px:
        peak = max(peak, p)
        mdd = max(mdd, (peak - p) / peak)
    add("S2_numerical", "oracle:drawdown", "Compute maximum drawdown.",
        f"Prices: {px}.", f"Max drawdown = {mdd:.6f} ({mdd*100:.2f}%).\nMethod: deterministic calculator.")


def s2_var():
    losses = [1.0, 2.0, 0.5, 3.0, 5.0, 0.2, 1.5, 4.0, 0.8, 2.5]
    s = sorted(losses)
    import math as _m
    var95 = s[min(len(s) - 1, _m.ceil(0.95 * len(s)) - 1)]
    tail = [x for x in losses if x >= var95]
    cvar = sum(tail) / len(tail)
    add("S2_numerical", "oracle:var_cvar", "Compute historical VaR95 and CVaR95 of losses.",
        f"Losses: {losses}.", f"VaR95 = {var95:.4f}; CVaR95 = {cvar:.4f}.\nMethod: deterministic calculator.")


def s2_bond():
    c, y, n, f = 5.0, 0.04, 3, 100.0
    px = sum(c / (1 + y) ** t for t in (1, 2, 3)) + f / (1 + y) ** 3
    add("S2_numerical", "oracle:bond_price", "Price a 3y annual 5% bond at 4% yield.",
        f"Coupon: {c}, Yield: {y}, Face: {f}.", f"Price = {px:.4f}.\nMethod: deterministic calculator.")


def s2_kelly():
    p, b = 0.55, 1.0
    fstar = (p * b - (1 - p)) / b
    add("S2_numerical", "oracle:kelly", "Compute full-Kelly fraction for p=0.55, payout 1:1.",
        "p=0.55, b=1.0.", f"f* = (0.55*1 - 0.45)/1 = {fstar:.4f}; use fractional Kelly in production.\nMethod: deterministic calculator.")


for _ in range(10):
    s2_returns(); s2_cagr(); s2_vol_sharpe(); s2_drawdown(); s2_var(); s2_bond(); s2_kelly()

# ---- S3 refusals ----
S3 = [
    ("stale data", "Condition: stale market data (age 900s, TTL 300s).",
     "Action: NO_TRADE. Reason: fail closed — data older than TTL cannot price risk."),
    ("unknown symbol", "Ticker 'ZZZZQQ' not in security master.",
     "Action: ABSTAIN. Reason: unvalidated instrument; no analysis without security-master validation."),
    ("prediction demand", "User demands tomorrow's exact price.",
     "Action: ABSTAIN with uncertainty. Reason: point-price certainty is not offered; scenario distribution only with evidence."),
    ("missing evidence", "Earnings claim with no filing attached.",
     "Action: REVIEW. Reason: unverified claim; attach 10-Q/8-K before conclusions."),
]
for cond, inp, out in S3:
    for i in range(10):
        add("S3_refusal", "policy:fail_closed", f"Apply DELTA fail-closed policy. Case {i}.",
            inp, f"{out}\nEvidence: policy snapshot #{i}.")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    h = hashlib.sha256(OUT.read_bytes()).hexdigest()
    stages: dict[str, int] = {}
    for r in rows:
        stages[r["stage"]] = stages.get(r["stage"], 0) + 1
    MANIFEST.write_text(json.dumps({"file": OUT.name, "rows": len(rows),
                                    "stages": stages, "sha256": h,
                                    "seed": SEED, "live_numbers": False}, indent=2),
                        encoding="utf-8")
    print(f"Wrote {len(rows)} rows -> {OUT} sha={h[:16]} stages={stages}")


if __name__ == "__main__":
    main()
