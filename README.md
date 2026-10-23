# DELTA OS — Institutional Quantitative Trading Operating System

![Version](https://img.shields.io/badge/version-2.15-blue.svg)
![Pytest](https://img.shields.io/badge/pytest-1358%20passed-brightgreen.svg)
![Cargo](https://img.shields.io/badge/cargo%20workspace-49%20passed-brightgreen.svg)
![Safety](https://img.shields.io/badge/governance-fail--closed-red.svg)
![Mode](https://img.shields.io/badge/status-PAPER%20green%20%7C%20LIVE%20fail--closed-orange.svg)

DELTA OS is an institutional-grade quantitative trading operating system designed for proprietary trading desks, quantitative researchers, portfolio managers, and risk officers.

**Terminal-Only Institutional Architecture (ADR-0006):** DELTA provides native terminal interfaces—the ultra-low latency Rust Ratatui 11-screen TUI and the OpenCode-unified Python CLI/REPL. Machine integration is provided via an asynchronous JSON-RPC 2.0 loopback bridge and Model Context Protocol (MCP) stdio servers without web or browser overhead.

---

## Key Subsystems & Capabilities

### 1. Master OpenCode CLI Parity Suite (39 Commands)
Direct, scriptable command-line interface mirroring and extending OpenCode (`opencode v2.0.26`) with finance-native institutional quantitative commands:

#### OpenCode Parity Commands (17 Core Subcommands)
- **`delta run`**: Headless quantitative execution with model selection, quantitative chain-of-thought (`--thinking`), session continuation, and JSON/NDJSON output.
- **`delta mini`**: Minimal interactive quantitative interface with session resumption, fast quoting, and rapid order staging.
- **`delta auth`**: Encrypted credentials vault management (`list`, `login`, `logout`, `export`) for Alpaca, IBKR, OpenAI, Anthropic, Gemini, DeepSeek, and FRED.
- **`delta models`**: Canonical model registry with live health probes (`READY`, `CONFIGURED`, `NEEDS_KEY`, `INVALID`).
- **`delta mcp`**: Stdio JSON-RPC 2.0 Model Context Protocol server exposing market data, technical indicators, and quantitative stats.
- **`delta session`**: Atomic session persistence in `~/.delta/session.json` with full lifecycle management (`show`, `list`, `clear`, `delete`, `export`, `import`).
- **`delta service`**: Background quantitative daemon controller (`start`, `stop`, `restart`, `status`, `logs`, `get`, `set`, `unset`) managing continuous 24/7 Sentinel surveillance with persistent schema-validated configuration (`~/.delta/service_config.json`).
- **`delta plugin`**: Extensible plugin manager (`list`, `add`, `remove`, `check`, `update`) for custom alphas, indicators, and broker connectors.
- **`delta stats`**: Institutional performance analytics (Sharpe, Sortino, VaR 99%, CVaR, Max Drawdown, Beta).
- **`delta debug`**: System diagnostics inspecting global paths (`debug paths`), registered agent fleet (`debug agents`), and environment variables (`debug config`).
- **`delta acp`**: Agent Client Protocol server for interoperability with external institutional AI agents and IDE copilots.
- **`delta api`**: Direct JSON-RPC bridge command dispatcher for automated pipelines.
- **`delta reload`**: Atomic configuration and session cache reload across active workspaces and models.
- **`delta pair`**: Cryptographically secure single-use HMAC pairing tokens (15-minute expiring TTL) for connecting remote terminals and copilots.
- **`delta serve`**: Real asynchronous JSON-RPC 2.0 HTTP loopback protocol bridge (`POST /rpc`, `GET /healthz`, `POST /pair`) on loopback `127.0.0.1:8765`.
- **`delta upgrade`**: Safe lifecycle management checking git release commits and verifying release artifacts.
- **`delta uninstall`**: Safe uninstallation preserving encrypted vault secrets, session state, and trade audit logs.

#### Quantitative & Institutional Native Commands (22 Subcommands)
- **`delta osint`**: Comprehensive multi-source OSINT dossier combining corporate identity, SEC EDGAR filings, Form 4 insider trades, filtered newswires, and FRED macro yields.
- **`delta chart`**: Dedicated in-terminal sectioned financial visualizations (candlesticks, RSI, MACD, L2 depth) powered by genuine QuoteFrame bars.
- **`delta catalyst`**: Real-time OSINT intelligence, SEC filings (10-K, 10-Q, 8-K), and sentiment analysis with anti-clickbait NLP firewall.
- **`delta mistakes`**: Self-learning episodic memory ledger inspecting past execution shortfalls, slippage, and learned lessons.
- **`delta trade`**: Canonical `OrderGateway` execution with Kelly sizing, Bayesian capital penalty, pre-trade risk firewall, and token-authenticated unlock.
- **`delta sentinel`**: 24/7 autonomous portfolio surveillance and automated max-drawdown circuit breaker wired directly to live broker state.
- **`delta broker`**: Multi-broker manager (`list`, `status`, `switch`) supporting Paper, Alpaca, IBKR, and FIX protocol.
- **`delta doctor`**: Comprehensive 11-path connectivity probe (market, broker, model, mcp, daemon, bridge, vault, clock).
- **`delta model-doctor`**: Local GPU and PyTorch/CUDA toolchain diagnostics with honest inference verification status.
- **`delta status`**: Dynamic runtime status inspection querying the active JSON-RPC bridge.
- **`delta research`**: Emits deterministic, reproducible quantitative experiment manifests with explicit `[RESEARCH PLAN ONLY - EXECUTION STAGED]` watermarks and SHA-256 dataset hashes.
- **`delta explain`**: Natural language multi-factor asset rationale and quantitative factor decomposition.
- **`delta mandate-wizard`**: Interactive investment policy and mandate definition wizard.
- **`delta scan`**: Quantitative multi-asset screener across universe and regimes.
- **`delta good-morning`**: Pre-market intelligence briefing with macro and earnings catalysts.
- **`delta portfolio-review`**: Authoritative portfolio factor exposure and risk breakdown.
- **`delta explain-trade`**: Post-trade attribution explaining execution mechanics, slippage, and fill quality.
- **`delta watch`**: Streaming real-time watchlist price monitor.
- **`delta plan-order`**: Pre-trade transaction cost and market impact simulation (Almgren-Chriss).
- **`delta learn`**: Record trade experiences into dual-persistence failure memory and durable SQLite WAL ledger.
- **`delta learning-status`**: Cryptographically verify SHA-256 hash-chain integrity of the outcome store.
- **`delta promote`**: Alpha strategy promotion gate verification across statistical hurdles.
- **`delta what-should-i-trade`**: Ranked opportunity radar ranked by expected Sharpe and risk-adjusted return.

---

### 2. Multi-Section In-Terminal Financial Visualizations
Rendered directly in the user's terminal window without external graphical or web dependencies:
- **ASCII/Unicode Candlestick OHLCV**: Dynamic price axis scaling, wicks, body coloring, timeframe selection (`1D`, `1H`, `15M`), and explicit provenance badges (`AVAILABLE`, `TIER1`, `PAPER`).
- **Volume Histogram Subplot**: Aligned beneath price bars.
- **RSI(14) Subplot**: Oversold (30) and overbought (70) threshold guide dashes with current indicator level.
- **MACD(12, 26, 9) Subplot**: MACD and signal line values with directional momentum histogram bars (`▲` / `▼`).
- **Level 2 Order Book Depth Ladder**: Real-time bid/ask ladders with size bars, explicit `[SYNTHETIC_DEMO]` watermarking for simulated depth, and **Order Book Imbalance Ratio (OBIR)**:
  $$\text{OBIR} = \frac{\sum \text{BidQty} - \sum \text{AskQty}}{\sum \text{BidQty} + \sum \text{AskQty}}$$
  Featuring directional bias indicators (`[BUY HEAVY]`, `[SELL HEAVY]`, `[BALANCED]`).

---

### 3. Canonical OMS Gateway & Execution Journal
- **Single Canonical Chokepoint**: All orders from REPL `/trade` and CLI `delta trade` route strictly through `core.oms.gateway.OrderGateway`.
- **Pre-Trade Risk Firewall**: In-memory validation enforcing net/gross notional caps, maximum leverage, price tolerance bands, data staleness guards, and kill switch enforcement prior to any network packet.
- **Idempotency & Role Enforcer**: Strict deduplication via client idempotency keys. Live broker execution requires verified `Role.RISK_OFFICER` authentication against `DELTA_UNLOCK_TOKEN`.
- **Three-Way Reconciliation**: Continuous validation across OMS memory, broker adapter state, and persistent ledger.

---

### 4. Portfolio Simplex Projection & Water-Filling Cap
- **Exact Bounded Simplex Projection**: In [`research/real_loop/portfolio_risk.py`](file:///home/unknownuser/Delta-/research/real_loop/portfolio_risk.py), `_cap()` guarantees $\sum w_i = 1.0 \pm 10^{-6}$ and $\max(w_i) \le \text{cap}$ via iterative water-filling.
- **Mathematical Invariant Preservation**: Replaced flawed heuristic clipping, eliminating weight re-inflation bugs.
- **Dynamic Feasibility**: Enforces $N \times \text{cap} \ge 1.0$ and scales bounds dynamically on small universes ($N < 4$) via `eff_max = max(max_weight, 1.0 / n)`.

---

### 5. Durable SHA-256 Hash-Chained Outcome Ledger
- **Tamper-Evident Storage**: [`learning/cli_outcome_store.py`](file:///home/unknownuser/Delta-/learning/cli_outcome_store.py) persists CLI executions, operator annotations, and failure attributions in SQLite WAL (`~/.delta/cli_outcomes.db`).
- **Cryptographic Hash Chaining**: Every record computes an immutable SHA-256 digest referencing `prev_hash`. The `delta learning-status` command validates ledger integrity.

---

### 6. 24/7 Autonomous Portfolio Sentinel Daemon
- Detached background process managing `DeltaSentinel` with atomic PID tracking (`~/.delta/daemon.pid`), structured logging (`~/.delta/daemon.log`), and persistent schema-validated configuration (`~/.delta/service_config.json`).
- Continuous non-blocking monitoring of equity, leverage, and margin limits wired directly to live broker router adapters.
- **Cross-Process Kill Circuit**: Automatically trips the fail-closed Kill Switch when portfolio drawdown breaches thresholds (default 2.0%), propagating immediately to all concurrent CLI, REPL, and OMS processes.

---

### 7. OSINT, SEC Filings & Alternative Data Intelligence
- **Comprehensive Institutional OSINT (`delta osint`)**: Multi-source dossier combining corporate identity, SEC filings, insider trades, filtered news, macro context, and social sentiment.
- **SEC EDGAR Tracking**: Parses official Form 10-K, 10-Q, and 8-K periodic disclosures with true accession numbers and Point-in-Time (PIT) validation. Uncataloged symbols return explicit `UNRESOLVED` without pseudo-CIK fabrication.
- **Form 4 Insider Intelligence**: Tracks C-Suite executive and Director buys, sells, option exercises, and grants with trade values.
- **Macroeconomic & Rate Regime**: Ingests FRED 10Y/2Y Treasury yields, automated 10Y-2Y yield curve inversion detection, VIX volatility regimes, and CPI inflation backdrop with honest `CACHED_BASELINE` badges when offline.
- **Anti-Clickbait & Anti-Disinformation Firewall**: Algorithmic NLP filtering suppressing hype, pump-and-dump tropes, and sensationalized retail headlines.
- **Social Buzz & Sentiment Divergence**: Computes retail chatter index vs. Wall Street analyst consensus, flagging euphoria vs. institutional accumulation divergence.

---

### 8. Universal Multi-Broker Routing & Fail-Closed Safety
- **Supported Brokers**: Authoritative In-Memory Paper Matching Engine, Alpaca Trade API v2, Interactive Brokers Client Portal Gateway, and FIX 4.2/4.4 protocol initiator.
- **Fail-Closed Live Gating**: Production live trading is strictly blocked by code (`ERR_LIVE_PROHIBITED`) until formal 14-day shadow soak evidence, isolated hardware benchmarks, and stakeholder sign-offs are completed.

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
python -m apps.cli.main chart NVDA --days 30 --timeframe 1D

# Real-time SEC filings & OSINT news dossier
python -m apps.cli.main catalyst AAPL

# Comprehensive institutional OSINT intelligence dossier
python -m apps.cli.main osint NVDA
python -m apps.cli.main osint NVDA --section news
python -m apps.cli.main osint NVDA --section filings
python -m apps.cli.main osint --section macro
python -m apps.cli.main osint NVDA --format json

# Start 24/7 background sentinel daemon
python -m apps.cli.main service start --max-dd 2.0
python -m apps.cli.main service status
python -m apps.cli.main service logs -n 20

# Review self-learning mistakes and failure attribution ledger
python -m apps.cli.main mistakes

# Verify outcome ledger hash-chain integrity
python -m apps.cli.main learning-status

# Submit institutional order with Kelly sizing and pre-trade interceptor
python -m apps.cli.main trade MSFT buy 50 --limit 420.00 --stop 410.00 --target 445.00

# Start headless JSON-RPC protocol bridge server
python -m apps.cli.main serve --hostname 127.0.0.1 --port 8765
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

#### Headless Protocol Bridge
```bash
python -m delta_os.bridge
```

---

## Testing & Institutional Verification Matrix

```bash
# 1. Run complete Python institutional test suite (1,358 passed, 0 failures, 6 skipped)
./.venv/bin/pytest -q

# 2. Run Rust Ratatui TUI and native workspace test suite (49 passed, 0 failures)
cargo test --workspace

# 3. Run canonical 12-stage end-to-end acceptance test suite (12 passed, 0 failures)
./.venv/bin/pytest tests/test_canonical_end_to_end.py -v

# 4. Run portfolio risk simplex cap invariant tests
./.venv/bin/pytest tests/test_portfolio_weight_cap.py -v

# 5. Run canonical OMS order gateway tests
./.venv/bin/pytest tests/test_canonical_trade_gateway.py -v

# 6. Run durable outcome store and CLI truthfulness tests
./.venv/bin/pytest tests/test_cli_learning_ledger.py tests/test_cli_truthfulness.py -v
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
