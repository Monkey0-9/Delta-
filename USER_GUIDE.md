# DELTA OS - Institutional Operator & User Guide

```
  ██████╗ ███████╗██╗  ████████╗ █████╗      ██████╗ ███████╗
  ██╔══██╗██╔════╝██║  ╚══██╔══╝██╔══██╗    ██╔═══██╗██╔════╝
  ██║  ██║█████╗  ██║     ██║   ███████║    ██║   ██║███████╗
  ██║  ██║██╔══╝  ██║     ██║   ██╔══██║    ██║   ██║╚════██║
  ██████╔╝███████╗███████╗██║   ██║  ██║    ╚██████╔╝███████║
  ╚═════╝ ╚══════╝╚══════╝╚═╝   ╚═╝  ╚═╝     ╚═════╝ ╚══════╝
  Institutional Quantitative Operating System & Execution Plane
```

DELTA is an institutional-grade, multi-language quantitative trading operating system designed for professional trading desks, quantitative researchers, and risk managers. It integrates market intelligence, quantitative alpha research, regime-aware portfolio optimization, pre-trade risk firewalls, low-latency execution engines, and cryptographic compliance into a unified terminal workspace.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites & System Setup](#2-prerequisites--system-setup)
3. [Running DELTA Locally](#3-running-delta-locally)
4. [TUI Interface & Navigation](#4-tui-interface--navigation)
5. [Unified Command Palette & Slash Commands](#5-unified-command-palette--slash-commands)
6. [Institutional Quantitative Workflows](#6-institutional-quantitative-workflows)
7. [Operational Truth & Provenance Badges](#7-operational-truth--provenance-badges)
8. [Java Execution Plane & FIX Engine](#8-java-execution-plane--fix-engine)
9. [Emergency Governance & Kill Switch Circuit](#9-emergency-governance--kill-switch-circuit)
10. [Troubleshooting & Diagnostics](#10-troubleshooting--diagnostics)

---

## 1. Architecture Overview

DELTA is built on a four-tier heterogeneous architecture designed for mechanical sympathy, fail-closed safety, and maximum mathematical throughput:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RUST RATATUI TUI                                │
│        11-View Real-Time Trading Terminal & Hardware Cursor            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ JSON-RPC 2.0 (IPC Bridge)
┌───────────────────────────────────▼────────────────────────────────────┐
│                    PYTHON QUANTITATIVE RUNTIME                         │
│   12-Stage Canonical Loop · Alpha Factory · AI Reasoning Models        │
└───────────────┬────────────────────────────────────────┬───────────────┘
                │ C-ABI (cdylib)                         │ TCP Loopback
┌───────────────▼───────────────┐        ┌───────────────▼───────────────┐
│     RUST NATIVE ACCEL         │        │     JAVA EXECUTION PLANE      │
│  Wilder RSI · Spearman IC     │        │  Disruptor SPSC Ring Buffer   │
│  ERC Solver · LOB Sweeps      │        │  Integer-Tick FIFO Matching   │
│  (delta_native.dll)           │        │  FIX 4.2 / 4.4 Stream Codec   │
└───────────────────────────────┘        └───────────────────────────────┘
```

1. **Rust Terminal Layer (`tui/`)**: High-performance, zero-flicker terminal user interface built on Ratatui. Renders 11 dedicated views (agents/execution/home/logs/markets/models/orders/portfolio/research/risk/system) with hardware-synchronized cursor placement, sub-millisecond redraws, and interactive command bars. The Python rail registers 18 screens (16 canonical workspaces incl. `data`, `reconciliation`, `audit`).
2. **Python Quantitative Engine (`core/`, `research/`, `delta_os/`)**: Orchestrates the 12-stage canonical institutional trading loop, walk-forward factor testing, portfolio allocation, and model-assisted research.
3. **Rust Native Numerical Kernels (`rust/`, `native/`)**: High-speed computational kernels compiled to `delta_native.dll`. Measured up to 131x over standard NumPy loops on Wilder RSI (see `BENCHMARKS.md`).
4. **Java Execution Plane (`execution/java_gateway/`)**: Pure-JDK 25 lock-free execution engine with cache-line-padded ring buffers and integer price matching. In-memory ring lanes certified at 14.2M ops/s; TCP loopback measured 17,711 msgs/s p50 48µs on this box (see `docs/PERF_RUNTIME_VERDICT.md`). PAPER/SIM rails only.

---

## 2. Prerequisites & System Setup

### Minimum System Requirements
- **OS**: Windows 10/11 64-bit, Linux (Ubuntu 22.04+ / RHEL 9+), or macOS (Apple Silicon / Intel).
- **RAM**: Minimum 8 GB (16 GB+ recommended).
- **CPU**: 4+ physical cores (tested on 20 logical cores).

### Software Toolchains
- **Python**: Version `3.11.x` or `3.12.x`.
- **Rust**: Version `1.80+` with `cargo` and MSVC or GCC build tools.
- **Java**: Oracle JDK or OpenJDK version `25` (`java` and `javac` on system `PATH`; measured on 25.0.1).

### Environment Variables
Configure the following recommended variables in your shell environment:

> **Secret hygiene:** the unlock token is a per-install secret. Never reuse a
> value from documentation, never commit it, and rotate it immediately if a
> value you used was ever published or shared. (An earlier revision of this
> guide published a working example token — treat that value as compromised
> and do not use it.)

```powershell
# PowerShell (Windows)
$env:OPENBLAS_NUM_THREADS = "1"     # Prevents excessive OpenBLAS thread allocation on high-core machines
$env:OMP_NUM_THREADS = "1"          # Constrains OpenMP pool size
$env:DELTA_UNLOCK_TOKEN = "SET_A_PRIVATE_TOKEN_HERE" # Per-install secret required to unlock the Kill Switch
```

```bash
# Bash / Zsh (Linux / macOS)
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
# Replace with your own per-install secret (never reuse a doc value):
export DELTA_UNLOCK_TOKEN="SET_A_PRIVATE_TOKEN_HERE"
```

---

## 3. Running DELTA Locally

DELTA provides four primary launch modes depending on whether you want a visual TUI terminal, an interactive quantitative REPL, a headless protocol bridge, or a standalone matching gateway.

### Mode 1: High-Performance Rust Ratatui TUI (Recommended)
Launches the full interactive 11-screen trading terminal:

```bash
# Debug Mode
cargo run --manifest-path tui/Cargo.toml

# Release Mode (Optimized)
cargo run --release --manifest-path tui/Cargo.toml
```

### Mode 2: Interactive Quantitative REPL
Launches the terminal-native Python research shell:

```bash
python -m delta_os
```

### Mode 3: Headless Protocol Bridge
Launches the JSON-RPC 2.0 background bridge for external client integration:

```bash
python -m delta_os.bridge
```

### Mode 4: Standalone Java Execution Gateway
Compiles and starts the high-speed Disruptor matching engine on port 9876:

```powershell
# Compile Java execution plane (quoted paths: safe when directory names contain spaces)
$src = (Get-ChildItem -Recurse -Filter *.java -Path "execution/java_gateway/src").FullName
javac -d "execution/java_gateway/bin" $src

# Start the gateway daemon
java -Xmx256m -cp execution/java_gateway/bin delta.execution.DeltaJavaGatewayServer 9876
```

---

## 4. TUI Interface & Navigation

The TUI features a disciplined top header, a dynamic primary workspace, and a bottom interactive command bar with an out-of-band emergency kill indicator.

### Global Hotkeys (verified against `delta_tui/keymap.py` — nothing here is aspirational)
| Keybinding | Action |
| :--- | :--- |
| `Ctrl+X` then key | Leader: `H` home, `M` market, `B` book, `R` research, `A` alpha, `P` portfolio, `K` risk cockpit, `E` execution, `O` orders, `S` system, `N` new research, `T` new session |
| `Ctrl+P` or `Ctrl+K` or `/` | Command palette (fuzzy `/re` → `/research` `/regime` `/risk` `/reconcile`) |
| `Tab` | Cycle between active panels |
| `Esc` | Clear input / dismiss modal / back |
| `Ctrl+X K` then `/kill CONFIRM` | **Emergency Kill**: bypasses LLM, hits risk governor directly. `Ctrl+C` never kills (cancels turn only); `Ctrl+K` alone never kills |

### The Terminal Screens (Python rail registers 18 — `delta_tui/app.py` SCREENS; Rust terminal renders 11 views; the 12 below are the primary operator workspaces — `tests/test_guide_proof.py` fails the build otherwise)

1. **Dashboard (`/desk`)**: HOME 4-pane — market, intelligence, portfolio, attention — with provenance badges.
2. **Markets (`/markets`)**: Real-time quotes, technical indicators (Wilder RSI, Bollinger Bands, MACD), and order book depth.
3. **Quant Lab (`/lab`)**: Factor alphas, information coefficients (IC), regime indicators, and walk-forward statistics.
4. **Portfolio (`/portfolio`)**: Multi-asset holdings, dollar allocations, target shares, and cash balances.
5. **Risk Firewall (`/risk`)**: Real-time VaR 95/99, Expected Shortfall (CVaR), macro stress test impacts (Treasury shock, oil shock, flash crash).
6. **Orders (`/orders`)**: Active order state machine, idempotency keys, execution statuses, and cancellations.
7. **Execution & SOR (`/exec`)**: Smart Order Router, FIX message audit, broker routing policies, and slippage TCA.
8. **Reconciliation (`/recon`)**: Three-way reconciliation engine comparing local OMS, broker confirmations, and position ledgers — `UNAVAILABLE` until a ledger triple is attached, never zero-filled.
9. **Cryptographic Audit (`/audit`)**: Tamper-evident SHA-256 chained audit log tail — `UNAVAILABLE` when no session records exist.
10. **System Configuration (`/config`)**: Broker connectivity status, MCP tool server health, and memory telemetry.
11. **Kill Switch & Safety (`/kill`, alias `/halt`)**: Emergency governance board, trigger causes, and authenticated unlock entry (`/unlock <token>` — wrong tokens are denied and logged, engine stays HALTED).
12. **Screen 12: Data (`/data`)** *(v2.0)*: Feed health per source (HEALTHY/DEGRADED/DOWN), data-quality verdict (PASS/WARN/FAIL), freshness age, dataset version, and PIT availability stamps. Shows `UNAVAILABLE` with source badges when no feed reports — never estimates.

### HOME 4-Pane Workspace *(v2.0)*

HOME answers on sight — **MARKET / INTELLIGENCE / PORTFOLIO / ATTENTION** — each figure carrying `SOURCE / AS-OF / FRESHNESS / CONFIDENCE` or `UNAVAILABLE`. Analysis renders **evidence cards** (per-factor for/against with weights, model + OOS IC, risk block) and a **consensus matrix** (Alpha/Regime/News/Risk/Portfolio votes → `CONFLICTED → REVIEW`), never bare sentiment.

---

## 5. Unified Command Palette & Slash Commands

DELTA features a unified slash-command language available across both the Rust TUI and Python REPL:

### Interactive Slash Autocomplete Dropdown

When typing in the command prompt or pressing `/`, DELTA renders an interactive, real-time autocomplete popup directly above the command line:

- **Real-Time Filtering**: Typing `/` followed by characters (e.g., `/an`, `/mo`, `/ri`) instantly filters the command catalog.
- **Orange Highlight Banner**: Active selections are highlighted with institutional orange (`RGB(249, 115, 22)`) matching Image 1.
- **Keybindings**:
  - `↑` / `↓` — Navigate through filtered commands.
  - `Tab` / `Enter` — Autocomplete the selected command into the prompt.
  - `Esc` — Dismiss the autocomplete dropdown.

### Quant AI Model Selector (`Ctrl+M`)

Pressing `Ctrl+M` or executing `/models` opens the Quant AI Model Selector modal matching Image 2:

- **Local Institutional Brain (`delta-fm-research`)**: Runs 100% offline with zero cloud API keys required. Handles multi-factor analysis, Black-Scholes Greeks, crash detection, forecasting, and algo-trading code generation.
- **Cloud / Custom Catalogue** (names match `delta_os/model_catalogue.py` BUILTIN exactly — use them verbatim with `/model switch <name>`):
    - `claude-3-7-sonnet` — Anthropic quant depth (key required)
    - `claude-5-5` — Anthropic latest template (key required)
    - `claude-opus-5-5` / `claude-sonnet-5-5` — Anthropic Opus / Sonnet 5.5 (key required)
    - `gpt-6-astra` / `gpt-6-1-sol` / `gpt-6-luna` — OpenAI Astra / Sol 6.1 / Luna (key required)
    - `gpt-4o` — OpenAI function-calling/tools (key required)
    - `deepseek-r1` — DeepSeek reasoning (key required)
    - `gemini-3-8-flash` / `gemini-2-5` — Google Gemini Flash 3.8 / long-context filings (key required)
    - `groq-free` — Groq fast inference (key required)
    - `astro-6-0` — Custom endpoint template · configure via `/models add <base-url>` (UNAVAILABLE until configured)
- **BYOK Key Management (`/key`)**: Configure API keys for cloud frontier models:

  ```bash
  /key anthropic sk-ant-api03-...
  /key openai sk-proj-...
  /key astro ak-astro-60-...
  ```

  Keys land in the AES-256 vault only (never disk-plaintext). Full flow:
  `set DELTA_VAULT_PASS=<pass>`, then `/auth`, then `/key <provider> <token>` —
  the catalogue flips `NEEDS_KEY` → `READY` and `/model switch` unlocks.

### Model Switching, Effort & Thinking *(v2.2 — switching routes inference, not labels)*

- `/model` — registry with `READY` / `NEEDS_KEY` / `UNAVAILABLE` badges; `[ACTIVE]` marks the routed model.
- `/model switch <name>` — pins the conversational inference role to that model's rail and prints `route=...`. Refusals are explicit: `NEEDS_KEY` names the `/key` fix, `UNAVAILABLE` names the `/models add` fix, rail-less templates refuse even when keyed (never a silent label-swap).
- `/effort <low|medium|high|xhigh|auto>` — applies timeout + token budget to the gateway (e.g. high = 60 s / 2048 tokens), persists across reboots, echoes in `/effort` with the live numbers.
- `/thinking <off|summary|activity>` — evidence verbosity for tool-backed answers: `OFF` hides tool evidence, `SUMMARY` counts tool calls (default), `ACTIVITY` shows the ledger. Persists across reboots.
- `/agent <name>` — switch persona (`research-agent` default; legacy `quant-researcher` maps to it). Unknown names list the 8 available personas instead of failing silently.

### Local Quant AI Brain Commands

- `/analyze <symbol>` — Comprehensive multi-factor analysis (Wilder RSI, MACD, Bollinger Bands, ATR, VWAP, beta, momentum score).
- `/risk <symbol>` — Multi-asset risk breakdown: equity VaR, Black-Scholes options Greeks ($\Delta, \Gamma, \nu, \Theta, \rho$, probability ITM), and futures margin leverage.
- `/forecast <symbol>` — Probabilistic return distribution forecast ($P(r > 0)$, expected return, timing signals for buying dips and taking profit at peaks).
- `/crash` — Regime-aware portfolio crash detection; generates pre-crash hedge warnings before major market downturns.
- `/news <symbol>` — Real-time stock headlines and sentiment catalyst correlation.
- `/sentinel [start|stop|status]` — 24/7 background AI watcher that monitors portfolio drawdown and enforces an automated loss kill switch.
- `/algo <statarb|vwap|momentum>` — Generates institutional production-grade Python algorithmic trading code (designed to the standard of top 0.001% quant engineers).
- `/ask <question>` — Local quantitative finance Q&A and conversational partner (or simply type any natural-language prompt).

### Navigation & Desk Commands

- `/markets [symbol]` — Switch to Markets view (optionally inspect symbol, e.g., `/markets NVDA`).
- `/portfolio` — Switch to Portfolio holdings and equity breakdown.
- `/orders` — Switch to Order Management System order book.
- `/desk` — Switch to Master Overview Desk.
- `/plan` — Switch to Strategy & Portfolio Rebalance Planning.
- `/mcps` — Toggle and inspect Model Context Protocol (MCP) server statuses.

### Data, Doctor & Status *(v2.0)*

- `/data` — Switch to the DATA workspace: feed health, quality verdict, freshness, dataset version, PIT stamps.
- `/doctor` — Connection doctor: 11 probes (yahoo/fred/paper/alpaca/ibkr/models/mcp/daemon/bridge/vault/clock) with READY/NEEDS_KEY/UNCONFIGURED states and fix hints. Current verdict: **GO-PAPER (6/11 READY)**.
- `/status` — Workspace + execution status: runtime, data, portfolio, risk, model, regime, broker, orders, MCP, GPU.

### Execution Modes *(v2.0: SHADOW is a true mode)*

| Mode | Data | Execution | Orders reach broker? |
| :--- | :--- | :--- | :--- |
| `LIVE` | live | real | YES — R10-gated, currently `ERR_LIVE_PROHIBITED` |
| `PAPER` | live | simulated fills | NO |
| `SHADOW` | live | hypothetical (recorded, never submitted) | NO — mirror-diff + 14-day soak artifact |
| `SIMULATION` | replay/synthetic | simulated | NO |
| `RESEARCH` | any | none (no orders) | NO |
| `DEMO` | synthetic showcase | simulated | NO — badged, never portfolio state |

### Execution & Safety Commands

- `/trade [side] [sym] [qty] [price]` — Submit pre-trade validated order.
- `/halt [reason]` or `/kill` — **Emergency Kill Switch**: Immediately halts all trading, cancels open orders, and locks broker gateways in-memory.
- `/unlock <token>` — Authenticated unlock from HALTED state using the security token (`$env:DELTA_UNLOCK_TOKEN`).

---

## 6. Institutional Quantitative Workflows

### Workflow 1: Market Intelligence & Technical Indicator Inspection
1. In the TUI or REPL, type `/markets NVDA`.
2. Inspect the **Wilder RSI (14)**, **MACD (12/26/9)**, and **Bollinger Bands** computed via accelerated Rust kernels.
3. Observe Point-in-Time (PIT) integrity: DELTA strictly prevents lookahead bias ($t_{event} \le t_{published} \le t_{available} \le t_{decision}$).

### Workflow 2: Quantitative Factor Research & Forecast
1. Switch to Quant Lab (`/lab`).
2. Run factor neutralization to isolate idiosyncratic stock alpha from market beta.
3. Inspect the return distribution forecast $P(r_{t+h} \mid X_t)$: expected return $\mu$, volatility $\sigma$, and 95% confidence intervals.

### Workflow 3: Portfolio Allocation & Pre-Trade Risk Firewall
1. DELTA uses a regime-aware half-Kelly optimization model:
   $$f^* = \frac{1}{2} \cdot \frac{\mu}{\sigma^2} \cdot \kappa_{\text{regime}}$$
2. The portfolio optimizer limits single-name concentration to $\le 20\%$ and total gross leverage to $\le 1.5\text{x}$.
3. Before any order is submitted, the **Pre-Trade Risk Firewall** performs non-bypassable in-memory checks:
   - Max single-order notional ($\le 25\%$ of equity).
   - Cash availability for buy orders.
   - Kill switch state verification (fail-closed).

### Workflow 4: Order Submission, Paper Matching & Three-Way Reconciliation
1. Submit an order via the command line or UI:
   `BUY 100 NVDA LIMIT 184.20`
2. The OMS stamps the order with a unique UUID and SHA-256 idempotency key to prevent double execution.
3. The execution engine routes the order to the paper broker, applying realistic market microstructure slippage:
   $$\text{Slippage (bps)} = \text{Half-Spread} + 5.0 \cdot \sqrt{\frac{Q}{\text{ADV}}}$$
4. Upon fill, the **Three-Way Reconciler** compares:
   - Internal OMS Order State
   - External Broker Fill Message
   - Position Ledger Equity
5. If any quantity or price discrepancy is detected, the pipeline immediately halts and flags `MISMATCH`.

### Workflow 5: Tamper-Evident SHA-256 Audit Trail
Every trade, parameter shift, and state change is cryptographically hashed:
$$\text{Hash}_i = \text{SHA256}(\text{Hash}_{i-1} \parallel \text{Timestamp} \parallel \text{Stage} \parallel \text{Payload})$$
View the verified immutable audit log anytime via `/audit`.

### Workflow 6: Shadow Validation & Evidence Review *(v2.0)*
1. Promote a validated candidate to `SHADOW`: live data flows in, decisions are recorded as hypothetical executions — **zero orders reach any broker**.
2. Track the **mirror-diff** (hypothetical vs realized action mismatch rate) and accumulate the **14-day soak artifact** (`SOAK_COMPLETE` only at ≥14 days, zero downtime).
3. Review any idea through its **evidence card** (for/against weights, model + OOS IC, marginal VaR, cost preview) and the **consensus matrix**; `CONFLICTED` forces `REVIEW`, never auto-trade.
4. The decision engine emits `NO_TRADE` (policy/risk block, reason-coded) vs `WAIT` (low confidence) — both are first-class outcomes, not errors.

---

## 7. Operational Truth & Provenance Badges

DELTA enforces an institutional **Truth Over Polish** invariant. The platform will **never display fabricated, mock, or hardcoded illustrative metrics** (such as arbitrary $1,000,000 balances or fake order tickets).

Every metric displayed on screen carries an explicit data provenance badge:

| Badge | Meaning |
| :--- | :--- |
| `LIVE` | Connected directly to an active, authenticated institutional broker / exchange feed. |
| `PAPER` | Executing against live tick data with calibrated Almgren-Chriss market impact models. |
| `SHADOW` *(v2.0)* | Live tick data in, hypothetical execution recorded, **never submitted** — mirror-diff + soak tracked. |
| `RESEARCH` | Research-only context: datasets, experiments, validation. No orders possible. |
| `DEMO` | Explicit synthetic showcase. Never portfolio state. |
| `SIM` | Running against historical tick-pit market replays with full PIT boundary enforcement. |
| `SYNTHETIC` | Statistically generated geometric Brownian motion / jump-diffusion data for stress testing. |
| `UNAVAILABLE` | Live broker or market data is offline. Figures are shown as `---` rather than estimated. |

---

## 8. Java Execution Plane & FIX Engine

For institutional trading operations requiring sub-microsecond matching and industry-standard FIX connectivity, DELTA includes a native Java execution gateway.

### Capabilities (measured — see `docs/PERF_RUNTIME_VERDICT.md`)
- **Lock-Free Disruptor Ring Buffer**: in-memory ring lanes certified at **14.2M ops/s** (documented-hardware runs); TCP loopback on this box measured **17,711 msgs/s, p50 48µs / p99 148µs** (`benchmarks/java_gateway_bench.json`). Quote the lane you mean — never the big number for the loopback job.
- **Price-Time FIFO Order Book**: Full support for limit orders, aggressor market orders, partial fills, and instant cancellations.
- **FIX 4.2 / 4.4 Engine**: Zero-copy parser and serializer for `Logon (35=A)`, `NewOrderSingle (35=D)`, and `ExecutionReport (35=8)` messages with strict tag-10 checksum validation.
- **Scope**: PAPER/SIM rails only. Live venue adapters are refusal stubs until R10 sign-off. No C#/JS layers: measured unnecessary (fourth runtime + extra IPC hops would add latency, not remove it).

### Python Integration
The Java execution plane can be consumed transparently from Python:

```python
from execution.adapters.java_gateway_adapter import JavaGatewayAdapter

# Auto-spawns and connects to Java Gateway
gateway = JavaGatewayAdapter(port=9876, auto_spawn=True)

# Ping health check
assert gateway.ping() is True

# Submit limit order to Java Disruptor matching engine
response = gateway.match_order(
    cl_ord_id="ORD-1001",
    symbol="NVDA",
    side="BUY",
    price=184.20,
    quantity=100
)
print("Java Fill Execution:", response)
```

---

## 9. Emergency Governance & Kill Switch Circuit

DELTA implements a fail-closed emergency circuit breaker governed by institutional safety rules:

```
[OPERATOR TRIGGER] ──> In-Memory Native Rejection (< 100 ns)
                              │
                      [NETWORK HARD DROP]
                              │
                      [BROKER FLUSH & CANCEL]
                              │
                      [AUTHENTICATED UNLOCK REQUIRED]
```

1. **Triggering the Kill Switch**:
    - In TUI: type `/kill` to arm, then `/kill CONFIRM` to engage — this bypasses the LLM and hits the risk governor directly. `Ctrl+C` cancels the current turn only; it never kills. `Ctrl+K` alone only opens the command palette.
    - In REPL: execute `/kill [reason]` (halts immediately). `Ctrl+C` cancels the current turn only (see `delta_os/repl.py`).
    - Automated: The Risk Firewall automatically trips if VaR limits are breached or broker disconnects occur.
2. **Behavior Under Halt**:
   - In-memory order entry is rejected immediately prior to any network transmission.
   - All open resting orders are cancelled across connected brokers.
   - The status banner pulses `CRITICAL: HALTED`.
3. **Unlocking**:
    - Unlocking cannot be performed through ordinary keystrokes or AI model prompts.
    - Requires explicit execution of `/unlock <token> [actor] [reason...]` using the per-install secret (`$env:DELTA_UNLOCK_TOKEN`); wrong tokens are denied and logged, engine stays HALTED.

---

## 10. Troubleshooting & Diagnostics

### High-Core Windows Thread Allocation (OpenBLAS Error)
If you encounter `OpenBLAS error: Memory allocation still failed after 10 retries` when importing NumPy on systems with 16+ logical cores:
```powershell
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
```

### Running the Full Test Suite
Verify that all system layers are functioning correctly:

```bash
# 1. Run Rust TUI & native kernel test suite (25 tests: lib 15 + integration 10)
cargo test --manifest-path tui/Cargo.toml

# 2. Run the full Python suite — v2.0: 961 passed (846 + 115 institutional)
python -m pytest tests/ -q

# 3. Stage proofs (29 tests) + audit-gap closure (3 tests)
python -m pytest tests/test_stage1_foundation.py tests/test_stage2_quantbrain.py tests/test_stage3_decision.py tests/test_stage4_validation.py tests/test_stage5_reality.py tests/test_audit_gaps.py -q

# 4. Connection doctor (expect GO-PAPER 6/11 READY; LIVE stays gated)
python scripts/system_doctor.py --connections

# 5. Run Java execution plane unit tests (4 tests)
java -cp execution/java_gateway/bin delta.execution.GatewayTests
```

---

*DELTA OS — Proprietary Institutional Quantitative Trading System*
