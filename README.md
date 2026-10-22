# DELTA OS — Institutional Quantitative Trading Operating System

![Version](https://img.shields.io/badge/version-2.10-blue.svg)
![Pytest](https://img.shields.io/badge/pytest-1261%20passed-brightgreen.svg)
![Cargo](https://img.shields.io/badge/cargo%20workspace-48%20passed-brightgreen.svg)
![Safety](https://img.shields.io/badge/governance-fail--closed-red.svg)
![Mode](https://img.shields.io/badge/status-PAPER%20green%20%7C%20LIVE%20fail--closed-orange.svg)

DELTA OS is an institutional-grade quantitative trading operating system designed for proprietary trading desks, quantitative researchers, portfolio managers, and risk officers.

**Terminal-Only Institutional Architecture (ADR-0006):** DELTA provides native terminal interfaces—the ultra-low latency Rust Ratatui 11-screen TUI and the OpenCode-unified Python CLI/REPL. Machine integration is provided via asynchronous JSON-RPC 2.0 bridge and MCP stdio protocols without web or browser overhead.

---

## Key Subsystems & Capabilities

### 1. Full OpenCode CLI Parity Suite
Direct, scriptable command-line interface mirroring and extending OpenCode (`opencode v2.0.26`) with finance-native institutional commands:
- **`delta run`**: Headless quantitative execution with model selection, quantitative chain-of-thought (`--thinking`), and JSON/NDJSON output.
- **`delta mini`**: Minimal interactive quantitative interface with session resumption, fast quoting, and rapid order staging.
- **`delta auth`**: Encrypted credentials vault management (`list`, `login`, `logout`, `export`) for Alpaca, IBKR, OpenAI, Anthropic, Gemini, DeepSeek, and FRED.
- **`delta models`**: Canonical model registry with live health probes (`READY`, `CONFIGURED`, `NEEDS_KEY`, `INVALID`).
- **`delta mcp`**: Stdio JSON-RPC 2.0 Model Context Protocol server exposing market data, technical indicators, and quantitative stats.
- **`delta session`**: Atomic session persistence in `~/.delta/session.json` tracking active workspace, theme, broker, model, and safety mode.
- **`delta service`**: Background quantitative daemon controller (`start`, `stop`, `restart`, `status`, `logs`) managing the continuous 24/7 Sentinel watcher via detached background processes.
- **`delta plugin`**: Extensible plugin manager (`list`, `add`, `remove`, `check`, `update`) for custom alphas, indicators, and broker connectors.
- **`delta stats`**: Institutional performance analytics (Sharpe, Sortino, VaR 99%, CVaR, Max Drawdown, Beta).
- **`delta debug`**: System diagnostics inspecting global paths (`debug paths`), registered agent fleet (`debug agents`), and environment variables (`debug config`).
- **`delta acp`**: Agent Client Protocol server for interoperability with external institutional AI agents and IDE copilots.
- **`delta api`**: Direct JSON-RPC bridge command dispatcher for automated pipelines.
- **`delta upgrade` & `delta uninstall`**: Safe lifecycle management preserving encrypted vault secrets and trade logs.

### 2. Multi-Section In-Terminal Financial Visualizations
Rendered directly in the user's terminal window without external graphical or web dependencies:
- **ASCII/Unicode Candlestick OHLCV**: Dynamic price axis scaling, wicks, body coloring, and explicit provenance badges (`AVAILABLE`, `TIER1`, `PAPER`).
- **Volume Histogram Subplot**: Aligned beneath price bars.
- **RSI(14) Subplot**: Oversold (30) and overbought (70) threshold guide dashes with current indicator level.
- **MACD(12, 26, 9) Subplot**: MACD and signal line values with directional momentum histogram bars (`▲` / `▼`).
- **Level 2 Order Book Depth Ladder**: Real-time bid/ask ladders with size bars and **Order Book Imbalance Ratio (OBIR)**:
  $$\text{OBIR} = \frac{\sum \text{BidQty} - \sum \text{AskQty}}{\sum \text{BidQty} + \sum \text{AskQty}}$$
  Featuring directional bias indicators (`[BUY HEAVY]`, `[SELL HEAVY]`, `[BALANCED]`).

### 3. Self-Learning Pre-Trade Interceptor
- **Persistent Episodic Memory**: Automatically records trade outcomes and failure attributions into `~/.delta/mistakes.jsonl`.
- **Pre-Trade Veto Invariant**: Prevents repeat mistakes by blocking toxic execution patterns (e.g., buying overbought RSI > 75 assets during `BEAR` or `BEAR_CRASH` regimes).
- **Adaptive Bayesian Risk Penalty**: Calculates asset-specific historical loss rates and dynamically scales position sizing (from 1.0 down to 0.25).
- **Audit Ledger**: Use `delta mistakes` or `/mistakes` to inspect attributed failures and learned lessons.

### 4. 24/7 Autonomous Portfolio Sentinel Daemon
- Detached background process managing `DeltaSentinel` with atomic PID tracking (`~/.delta/daemon.pid`) and detached logging (`~/.delta/daemon.log`).
- Continuous non-blocking monitoring of equity, leverage, and margin limits.
- **Automated Loss Circuit Breaker**: Automatically trips the fail-closed Kill Switch when portfolio drawdown breaches tolerable thresholds (default 2.0%).

### 5. OSINT, SEC Filings & Alternative Data Intelligence
- **SEC EDGAR Tracking**: Parses official 10-K, 10-Q, and 8-K filings for material corporate disclosures.
- **Macroeconomic Backdrop**: Ingests FRED 10-year Treasury yields, yield curve slopes, and VIX volatility.
- **Anti-Clickbait Filter**: Algorithmic regex filtering that removes sensationalized retail noise, producing sentiment scores with verifiable provenance (`TIER1_SEC`, `TIER1_VERIFIED`).

### 6. Universal Multi-Broker Routing & Fail-Closed Safety
- **Supported Brokers**: Authoritative In-Memory Paper Matching Engine, Alpaca Trade API v2, Interactive Brokers Client Portal Gateway, and FIX 4.2/4.4 protocol initiator.
- **Fail-Closed Live Gating**: Production live trading is strictly blocked by code (`ERR_LIVE_PROHIBITED`) until formal 14-day shadow soak evidence and stakeholder sign-offs are completed.

---

## Quickstart & CLI Usage

### 1. Installation & Environment Setup
```bash
# Clone repository
git clone https://github.com/Monkey0-9/Delta-.git
cd Delta-

# Provision virtual environment and dependencies
./.venv/bin/pip install -r requirements.txt
```

### 2. Launching Interfaces

#### Master OpenCode CLI
```bash
# Headless quantitative prompt execution
python -m apps.cli.main run "Analyze current SPY regime and macro backdrop" --thinking

# Dedicated in-terminal candlestick, indicator, and depth chart
python -m apps.cli.main chart NVDA --days 30

# Real-time SEC filings & OSINT news dossier
python -m apps.cli.main catalyst AAPL

# Start 24/7 background sentinel daemon
python -m apps.cli.main service start --max-dd 2.0
python -m apps.cli.main service status
python -m apps.cli.main service logs -n 20

# Review self-learning mistakes and failure attribution ledger
python -m apps.cli.main mistakes

# Submit institutional order with Kelly sizing and pre-trade interceptor
python -m apps.cli.main trade MSFT buy 50 --limit 420.00 --stop 410.00 --target 445.00
```

#### Native Rust Ratatui 11-Screen Terminal
```bash
# High-performance TUI with Tokio async IPC
cargo run --manifest-path tui/Cargo.toml
```

#### Interactive Python Quantitative REPL
```bash
python -m delta_os
```

#### Headless JSON-RPC Bridge
```bash
python -m delta_os.bridge
```

---

## Testing & Institutional Verification Matrix

```bash
# 1. Run complete Python institutional test suite (1,261 passed, 0 failures)
./.venv/bin/pytest -v

# 2. Run Rust Ratatui TUI and native workspace test suite (48 passed, 0 failures)
cargo test --workspace

# 3. Run OpenCode unified CLI test suite
./.venv/bin/pytest tests/test_unified_cli.py -v

# 4. Run in-terminal financial visualization tests
./.venv/bin/pytest tests/test_terminal_chart.py -v

# 5. Run pre-trade mistake interceptor tests
./.venv/bin/pytest tests/test_pretrade_interceptor.py -v
```

---

## Non-Negotiable Institutional Governance Rules

1. **Truth Over Polish**: Never display fake or hardcoded illustrative metrics. All figures must reflect live data, paper state, or explicit `UNAVAILABLE` indicators with clear provenance badges.
2. **Fail-Closed Risk**: Emergency kill switches must enforce native in-memory rejection of orders prior to any network hop, followed by verified enforcer confirmation.
3. **Point-in-Time Temporal Integrity**: No lookahead bias is permitted across decision boundaries ($t_{\text{event}} \le t_{\text{published}} \le t_{\text{available}} \le t_{\text{decision}} \le t_{\text{execution}}$).
4. **Submission Idempotency**: All orders must specify unique idempotency keys to prevent duplicate execution across retries.
5. **Authenticated Unlock**: Unlocking from a `HALTED` state requires a verified authentication token (`DELTA_UNLOCK_TOKEN`) with `Role.RISK_OFFICER` rank.

---

## License

Proprietary — Institutional Use Only.
