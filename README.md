# DELTA — Finance-Native Autonomous Intelligence Platform

Paper/sim-only build. No live broker adapters.

## Quickstart

```powershell
pip install -e ".[dev]"
python -m pytest tests validation -q
python -m benchmark.runner --size 10000 --iterations 10
```

## Three-language architecture

- **Python** — research + intelligence: `quant/`, `research/`, `finance_model/`,
  `agents/`, `learning/`, `memory/`, `validation/`, `portfolio/`, `world_model/`,
  `decision/`, `simulation/`. Reference implementation for every kernel.
- **Rust** (`rust/src/`) — infrastructure/data plane: execution gateway,
  rate limiting, backpressure queue, reconnect backoff, durable hash-chained
  log, paper connector + ingestion pipeline, parity kernels. PyO3 `delta_native`.
- **C++** (`native/cpp/`) — latency-critical reference kernels: L2 book,
  price-time matching, microstructure, rolling/EMA/RSI features, risk and
  portfolio math, execution sweep. C ABI (`cabi.cpp`) + parity driver.

Rule: Python reference → benchmark → profile → native only with parity proofs.
Native must never bypass the deterministic risk firewall or authorization.

## Architecture

`Data (PIT) -> WorldState -> Quant -> Research -> Finance Intelligence (local LLM, grounded) -> Portfolio/Risk Firewall -> Execution OMS -> Paper Broker -> Attribution -> Memory/Learning`

Invariants: no agent-to-broker path, stale data blocks live intent, idempotency keys, reconstructable decisions, versioned models, protected-failure regression, replayable events, independent kill switch.

## Key modules

- `data/point_in_time/store.py` — as-of store, duplicate drop, dataset hash
- `market_data/` — Quote/Trade/Bar/OrderBook + Normalizer + validators
- `world_model/state_fusion/fusion.py` — deterministic fusion + `state_hash`
- `quant/signals|factors|forecasting|regime|portfolio|uncertainty` — research engine
- `simulation/` — replay/backtest/costs/scenarios/digital twin
- `finance_model/grounding.py` — claim `[evidence_id]` citation gate
- `risk/firewall/firewall.py` — FIA-style pre-trade firewall + `KillSwitch`
- `execution/engine/engine.py` — OMS lifecycle; `brokers/simulator` — paper fills
- `validation/` — walk-forward/OOS/stress/protected regression
- `rust/src/lib.rs` + `rust/cpp/checksum.cpp` — native parity kernels (Rust+C++)
- `config/paper.yaml` — numeric limits v1

See `docs/ANALYSIS.md` for full plan analysis and `DELTA.docx` v1.1 for the master spec.
