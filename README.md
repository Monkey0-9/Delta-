# DELTA OS - Institutional Quantitative Trading Operating System

A professional-grade quantitative trading operating system designed for institutional traders, quantitative researchers, and risk managers.

## Key Capabilities

- **Native Rust Ratatui TUI**: 11-screen terminal (Home, Research, Markets, Portfolio, Risk, Orders, Execution, Models, Agents, System, Logs) powered by Tokio async IPC.
- **12-Stage Canonical Pipeline**: Real data → PIT verification → Technical Indicators → Factor Alpha → Return Forecasting → Market Regime → Constrained Portfolio → Risk Firewall → OMS → Paper Broker → Three-Way Reconciliation → Chained SHA-256 Audit.
- **Fail-Closed Risk & Safety**: Multi-layer pre-trade risk firewall, anti-tilt behavioral controls, and a Rust-native emergency kill-switch circuit.
- **Microsecond Execution & Matching**: C++ / Rust limit order book, Almgren-Chriss market impact modeling, and automated three-way fill reconciliation.
- **Multi-Model Research Gateway**: Hot-swappable LLM router for natural-language quantitative queries, research synthesis, and macroeconomic reasoning.

---

## Installation & Launch

### 1. Python Environment Setup
```bash
# Clone repository
git clone https://github.com/Monkey0-9/Delta-.git
cd Delta-

# Install Python quantitative dependencies
pip install -r requirements.txt
```

### 2. Launching DELTA

#### Native Rust Ratatui TUI (Recommended)
```bash
# Build and run the native terminal interface
cargo run --manifest-path tui/Cargo.toml
```

#### Interactive Python Quantitative REPL
```bash
# Launch the Python quantitative shell
python -m delta_os
```

#### Headless JSON-RPC Bridge (For Automation & Scripting)
```bash
# Launch the headless protocol bridge over stdin/stdout
python -m delta_os.bridge
```

---

## Repository Architecture

```
Delta/
├── core/                  # Canonical pipeline, domain contracts, and risk engine
│   ├── canonical_pipeline.py  # 12-stage institutional quantitative loop
│   └── domain/                # Canonical domain models (Asset, Quote, Order, Risk)
├── tui/                   # High-performance Rust Ratatui 11-screen trading terminal
│   ├── src/bridge/            # Async JSON-RPC 2.0 client & typed protocol
│   ├── src/views/             # Real-time screens (Markets, Risk, Portfolio, Execution)
│   └── src/app.rs             # Application event loop & Rust-native kill circuit
├── delta_os/              # Quantitative runtime and headless IPC bridge
│   ├── bridge.py              # JSON-RPC 2.0 bridge with priority out-of-band lane
│   ├── repl.py                # Command dispatch and session persistence
│   └── safety.py              # Pre-trade safety governor and authenticated unlock
├── data/                  # Market data engine and temporal integrity
│   ├── market/                # Exchange trading calendar (NYSE / NASDAQ)
│   └── tick_pit/              # Point-in-Time (PIT) multi-timestamp validation
├── execution/             # Order management and transaction cost modeling
│   ├── cost_engine.py         # Calibrated transaction cost analysis
│   └── reconciliation/        # Three-way reconciliation (OMS vs Broker vs Ledger)
├── research/              # Quantitative alpha and factor lab
│   ├── alpha_contract.py      # Unified alpha contract and validation pipeline
│   └── real_loop/             # Walk-forward analysis and feature extraction
├── governance/            # Regulatory compliance and audit ledger
│   ├── kill_switch.py         # Enforced emergency circuit breakers
│   └── compliance.py          # SHA-256 tamper-evident event logging
├── native/                # Accelerated numerical kernels and LOB
│   ├── lob.py                 # Integer-tick order book
│   └── rust/                  # Native Rust modules
└── tests/                 # Comprehensive test suite (unit, integration, property, chaos)
    └── test_canonical_end_to_end.py  # 12-stage canonical acceptance tests
```

---

## Testing & Verification

Run the comprehensive test matrix:

```bash
# 1. Run 12-stage canonical end-to-end acceptance suite
python -m pytest tests/test_canonical_end_to_end.py -v

# 2. Run core quantitative test suite
python -m pytest tests/test_real_loop.py tests/test_trading_calendar.py -v

# 3. Run Rust TUI and native workspace test suites
cargo test --workspace
```

---

## Security & Governance Rules

1. **Truth Over Polish**: No hardcoded mock values. Metrics display provenance (`LIVE`, `PAPER`, `SIM`, `SYNTHETIC`, `UNAVAILABLE`) and as-of timestamps.
2. **Fail Closed**: In any ambiguous state, order routing is blocked. The kill switch blocks execution in-memory on the native Rust frontend and verifies backend confirmation before displaying `HALTED`.
3. **Authenticated State Transitions**: Emergency unlock requires authentication via `DELTA_UNLOCK_TOKEN` and is permanently recorded in the cryptographic audit ledger.

---

## License

Proprietary — Institutional Use Only.
