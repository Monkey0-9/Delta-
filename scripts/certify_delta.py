"""DELTA production certification gate (W123 light).

Fails closed on:
- synthetic bars reachable in DATA_MODE=LIVE
- template LLM reachable without explicit allow_template
- non-deterministic paper order IDs
- inverse-vol masquerading as true risk parity
- missing research-statistics evidence in full cycle
"""
from __future__ import annotations

import os


def main() -> int:
    os.environ.pop("DATA_MODE", None)  # ensure LIVE default
    failures: list[str] = []

    # 1. LIVE must raise, never synthesize
    from research.real_loop import market_data as M

    if M.data_mode() != "LIVE":
        failures.append("default DATA_MODE is not LIVE")
    try:
        M.fetch_bars(["INVALID_SYMBOL_XYZ_123"], days=90)
        failures.append("LIVE fetch of invalid symbol did not raise MarketDataUnavailable")
    except M.MarketDataUnavailable:
        pass

    # 2. LLM must raise without template
    from research.real_loop import llm_agent as LLM

    ev = [LLM._evid("alpha", {"kind": "recommendation", "symbol": "TST", "action": "BUY",
                              "er_pct": 1.0, "vol_pct": 2.0, "confidence": 0.5,
                              "weight_pct": 5.0})]
    # point backends at dead ports so no real model can answer
    os.environ["OPENAI_BASE_URL"] = ""
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:1"
    try:
        LLM.synthesize("probe?", ev, allow_template=False)
        failures.append("synthesize(allow_template=False) did not raise LLMUnavailable")
    except LLM.LLMUnavailable:
        pass

    # 3. deterministic paper IDs
    from research.real_loop import paper_broker as PB

    a = PB.PaperLedger(cash=1_000_000, seed=99)
    b = PB.PaperLedger(cash=1_000_000, seed=99)
    oa = a.submit("AAPL", "BUY", 10, 100.0, idempotency_key="k1")
    ob = b.submit("AAPL", "BUY", 10, 100.0, idempotency_key="k1")
    if oa.order_id != ob.order_id:
        failures.append(f"paper order IDs non-deterministic: {oa.order_id} != {ob.order_id}")
    if "time" in oa.order_id.lower():
        failures.append("order ID leaks wall-clock")

    # 4. true risk parity ~= equal risk contribution
    import pandas as pd
    import numpy as np

    from research.real_loop import portfolio_risk as PR

    cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.01]], index=["A", "B"], columns=["A", "B"])
    tgt = PR.optimize({"A": 0.01, "B": 0.01}, cov, method="risk_parity_true",
                      max_weight=0.9)
    w = np.array([tgt.weights["A"], tgt.weights["B"]])
    rc = w * (cov.values @ w)
    if abs(rc[0] - rc[1]) / max(rc.sum(), 1e-12) > 0.05:
        failures.append(f"true risk parity RC unequal: {rc}")
    for m in ("mean_variance", "black_litterman", "hrp", "min_variance",
              "max_diversification", "cvar", "max_sharpe_tilt", "risk_parity_inv"):
        try:
            PR.optimize({"A": 0.01, "B": 0.02}, cov, method=m)
        except Exception as exc:
            failures.append(f"optimizer {m} raised: {exc}")

    # 5. research stats bundle
    from research.real_loop import validate as V

    bars = M.synthetic_bars("CERT", days=150)
    from research.real_loop import features as F

    feat = F.compute_features(bars.frame, "CERT", bars.data_hash)
    st = V.research_statistics(bars.frame, feat)
    for k in ("ic", "icir", "dsr", "pbo", "hac_t", "gate"):
        if k not in st:
            failures.append(f"research_statistics missing {k}")

    if failures:
        print("CERTIFICATION FAILED:")
        for f in failures:
            print(f" - {f}")
        return 1
    print("CERTIFICATION PASSED: fail-closed truth paths + deterministic replay + "
          "true-RP + research stats verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
