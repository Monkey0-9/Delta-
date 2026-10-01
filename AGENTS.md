# DELTA OS - Developer & Agent Guide

## Project Overview

DELTA OS is an institutional-grade quantitative trading operating system designed for professional traders, quantitative researchers, and sophisticated investors.

## Modern Architecture

```
Delta/
├── core/                  # Canonical pipeline, domain contracts, and risk engine
│   ├── canonical_pipeline.py  # 12-stage institutional quantitative loop
│   └── domain/            # Canonical domain contracts (Asset, Quote, Order, Risk)
├── tui/                   # High-performance Rust Ratatui 11-screen trading terminal
│   ├── src/bridge/        # Async JSON-RPC 2.0 client with request-id mapping
│   ├── src/views/         # Real-time views (Markets, Risk, Portfolio, Execution)
│   └── src/app.rs         # Event loop & Rust-native kill circuit
├── delta_os/              # Quantitative runtime and IPC bridge
│   ├── bridge.py          # JSON-RPC bridge with non-blocking priority lane
│   ├── repl.py            # Terminal REPL dispatch & session handling
│   └── safety.py          # Pre-trade safety governor & authenticated unlock
├── data/                  # Market data engine and temporal integrity
│   ├── market/            # Exchange trading calendar (NYSE / NASDAQ)
│   └── tick_pit/          # Point-in-Time (PIT) multi-timestamp validation
├── execution/             # Order management and transaction cost modeling
│   ├── cost_engine.py     # Calibrated transaction cost analysis
│   └── reconciliation/    # Three-way reconciliation (OMS vs Broker vs Ledger)
├── research/              # Quantitative alpha and factor lab
│   ├── alpha_contract.py  # Unified alpha contract and validation pipeline
│   └── real_loop/         # Walk-forward analysis and feature extraction
├── governance/            # Regulatory compliance and audit ledger
│   ├── kill_switch.py     # Enforced emergency circuit breakers
│   └── compliance.py      # SHA-256 tamper-evident event logging
└── native/                # Accelerated numerical kernels and LOB
    ├── lob.py             # Integer-tick order book
    └── rust/              # Native Rust acceleration
```

## Running DELTA

```bash
# Launch Native Rust Ratatui TUI
cargo run --manifest-path tui/Cargo.toml

# Launch Interactive Python Quantitative REPL
python -m delta_os

# Run Headless Protocol Bridge
python -m delta_os.bridge
```

## Key Invariants & Non-Negotiable Rules

1. **Truth Over Polish**: Never display fake or hardcoded illustrative metrics. All figures must reflect live data, paper state, or explicit `UNAVAILABLE` indicators with clear provenance badges.
2. **Fail-Closed Risk**: Emergency kill switches must enforce native in-memory rejection of orders prior to any network hop, followed by verified enforcer confirmation.
3. **Point-in-Time Temporal Integrity**: No lookahead bias is permitted across decision boundaries ($t_{event} \le t_{published} \le t_{available} \le t_{decision} \le t_{execution}$).
4. **Submission Idempotency**: All orders must specify unique idempotency keys to prevent duplicate execution across retries.
5. **Authenticated Unlock**: Unlocking from a HALTED state requires a verified authentication token (`DELTA_UNLOCK_TOKEN`).

## Testing & Verification

```bash
# Run 12-stage canonical end-to-end acceptance tests
python -m pytest tests/test_canonical_end_to_end.py -v

# Run Rust TUI and native workspace test suite
cargo test --workspace
```

## License

Proprietary — Institutional Use Only
