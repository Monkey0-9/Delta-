# DELTA TUI — OpenCode Interaction + Bloomberg Density + Quant Workflow

> Companion to `2026-10-05-delta-complete-os.md` (Stage 5 / UI-1→UI-5).
> OpenCode is a UX reference only — never a dependency. Delta stays
> Rust → Runtime → AI → ML → Research → Risk → Execution.

## 1. Target architecture

```text
                DELTA TUI
                   │
   ┌───────────────┼────────────────────┐
   │               │                    │
 COMMAND         AI                  DATA
 SYSTEM        SYSTEM               SYSTEM
   │               │                    │
 /model          /ask               /market
 /agent          /research           /news
 /mcp            /explain            /fund
 /risk           /forecast           /macro
 /backtest       /compare            /portfolio
   │               │                    │
   └───────────────┼────────────────────┘
                   │
             DELTA RUNTIME
                   │
  ┌────────────────┼─────────────────┐
  │                │                 │
RESEARCH        DECISION         EXECUTION
  │                │                 │
Alpha            Risk              OMS
Regime           Portfolio         Broker
News             Policy            Reconcile
ML               Firewall          Audit
```

## 2. The mistake to avoid

Not a chatbot screen (`> Ask Delta anything...` + `AI: ...`). The operator runs a
financial intelligence system. HOME must answer on sight: happening, changed,
belief, confidence, risk, portfolio, attention-required.

## 3. HOME (4 panes + command line + shortcut bar)

```text
╭─ DELTA ───────────────────────────────────────────────────────────────╮
│ LIVE   AAPL  NVDA  MSFT  SPY  QQQ        REGIME: HIGH-VOL  21:14:32 │
├───────────────────────────────────────────────────────────────────────┤
│  MARKET                          DELTA INTELLIGENCE                   │
│  SPY     +0.42%                 Signal     NEUTRAL                    │
│  QQQ     +0.71%                 Confidence  67%                      │
│  NVDA    -0.83%                 Regime      HIGH VOL                  │
│  AAPL    +0.21%                 Risk        ELEVATED                  │
│  PORTFOLIO                       ATTENTION                            │
│  NAV       $XXX                  ⚠ NVDA volatility ↑                 │
│  P&L       +X.XX%                ⚠ Fed event approaching              │
│  VaR       X.XX%                 • 3 model disagreements              │
│  CVaR      X.XX%                 • New AAPL filing                    │
├───────────────────────────────────────────────────────────────────────┤
│ > Ask Delta...                                                       │
├───────────────────────────────────────────────────────────────────────┤
│ /help /market /research /portfolio /risk /model /agent /mcp          │
└───────────────────────────────────────────────────────────────────────┘
```

`$XXX` renders only from live/paper state; otherwise `UNAVAILABLE` with
SOURCE/AS-OF/FRESHNESS/CONFIDENCE badges (existing `NO_DEMO_STATE` rule).
Current truth: `delta_tui/screens/home.py:31-38` splash-only and
`tui/src/views/home.rs:24-30` State-A/B — both need the 4-pane upgrade.

## 4. Command system (OpenCode philosophy, Delta commands)

Core: `/help /status /about /version /quit`.
AI: `/model /models /agent /agents /think /context /memory`.
Market: `/market /quote /chart /watchlist /sector /macro`.
Research: `/research /hypothesis /experiment /backtest /compare /validate /benchmark`.
Portfolio: `/portfolio /positions /exposure /attribution /optimize /rebalance`.
Risk: `/risk /var /cvar /stress /scenario /correlation /liquidity`.
Execution: `/orders /order /execution /fills /reconcile /broker` (+ `/cancel /flatten /kill`).
AI infra: `/mcp /mcps /tools /skills /providers`.
System: `/logs /audit /health /metrics /diagnostics /config` (+ `/doctor`).

Current truth: Python `delta_tui/commands/registry.py:9-16` lacks
aliases/args/permissions/completion/handler; Rust `tui/src/commands/registry.rs:66-77`
is richer but dispatch is hardcoded in `app.rs:178-507`; `/skills /providers`
missing everywhere; `/doctor /status /sessions /tools /chart /backtest` partial.
Converge on one `CommandRegistry` (name/aliases/description/arguments/permissions/
completion/handler) generated from `config/commands.toml`.

## 5. `/model` — selector, not switcher

LOCAL `Delta-Finance-7B READY 6.1GB CUDA 42 tok/s`; QUANT `Delta-Alpha-v12`,
`Delta-Regime-v4`, `Delta-Risk-v7` with READY/SHADOW/CANDIDATE; PROVIDERS
Anthropic/OpenAI/Google as `API KEY REQUIRED`. External optional; Delta native
default. Exists as stubs (`commands/registry.py:50`, `tui/.../registry.rs:233`).

## 6. `/agent` — real Delta agents

Researcher (hypothesis→experiment→evaluation), Market Analyst, News Analyst
(events+novelty+impact), Portfolio Analyst, Risk Officer (VaR/CVaR/stress/limits),
Execution Analyst (slippage/liquidity/quality), Quant Researcher
(alpha+backtest+validation), Orchestrator. Map to `delta_tui/app.py:45-47 AGENTS`
+ `tui/src/views/agents.rs` — never generic coding agents.

## 7. `/mcp` — first-class, risk-bounded

Table `market-data / sec-filings / news / broker:PAPER / research : CONNECTED`,
`quantconnect : DISABLED`; actions Details/Add/Toggle/Reconnect/Diagnostics.
MCP supplies context; an MCP server can never place orders or bypass
`risk/firewall` + `security/permissions.py`. Exists (`registry.py:52`,
Rust `:281`).

## 8. `@` — financial references

`@AAPL @NVDA @portfolio @research/experiment-042 @news/2026-10-05
@model/Delta-Alpha-v12 @risk/current @SEC/AAPL`, e.g.
`Analyze @AAPL using @portfolio and @risk/current`.
Exists but diverged: Python `context_resolver.py:11-21` vs Rust
`input/context.rs:46-86` — unify to one resolver set.

## 9. `!` — allowlist shell only

`!pytest !cargo test !git status !delta doctor !delta benchmark` inject output as
tool results. Missing in both stacks (correct to gate). Trading verbs
(`/order /cancel /flatten /kill`) are never reachable via `!`; they stay typed
with `confirmation_required` + `state_changing` flags.

## 10. Palette + conversation + status bar

`Ctrl+P` (and `Ctrl+K` per spec — move risk cockpit to `Ctrl+Shift+R`) palette with
Research/Portfolio/Risk/AI groups; fuzzy `/re → /research /regime /risk /reconcile`
and `/research → new/list/run/compare/validate/report`. Exists as filter-only
(Python `commands/palette.py:7`, Rust `commands/palette.rs:153`) — add the
dropdown renderer + cursor-aware `get_active_query` parity.

Conversation renders evidence cards, never bare sentiment:

```text
╭─ DELTA ANALYSIS ─────────────────────────────────────────╮
│ NVDA  Signal: MODERATELY BULLISH  Confidence: 71%        │
│ Regime: HIGH-VOLATILITY  Horizon: 5D                     │
│ EVIDENCE  ✓ Momentum +0.62  ✓ Earnings rev +0.31         │
│           ~ News +0.14  ✗ Volatility -0.28  ✗ Val -0.11  │
│ MODEL Delta-Alpha-v12  OOS IC: 0.087  Calibration: 0.94 │
│ RISK Marginal VaR: X  CVaR: X  Concentration: HIGH       │
│ [r] Research [b] Backtest [p] Portfolio [x] Risk         │
╰──────────────────────────────────────────────────────────╯
```

Status bar persistent on ALL screens incl. HOME
(fix `layout/breakpoints.rs:85-103` hiding it + `app.rs:971-983`;
wire Python `widgets/chrome.py:247-252` into `app.py:563-593`):
`DELTA │ LIVE │ CUDA │ DATA OK │ MODEL │ PAPER │ tickers │ REGIME │ RISK`.

## 11. Design language

Near-black base; green = positive/healthy, red = risk/negative,
yellow = warning, blue = information, purple = AI/research, gray = secondary —
no rainbow. Monospace, dense, short labels, aligned numerics, consistent spacing.

## 12. Screens (12) + overlays

`HOME MARKET RESEARCH PORTFOLIO RISK ORDERS EXECUTION MODELS AGENTS DATA SYSTEM
LOGS` — add missing DATA in both stacks (Rust 11/12, Python missing
DATA/AGENTS/LOGS as screens); demote extras to overlays. Overlays already exist
(~7: order-ticket/palette/kill/help/selector/context/slash) — add
evidence/Why/order-confirm; never 40 screens. Config-driven:
`config/tui.toml + commands.toml + keybinds.toml + theme.toml` (today all
hardcoded: `tui/src/theme.rs:11-42`, `delta_tui/themes.py:6-33`,
`layout/breakpoints.rs:18-47`, both registries, `delta_tui/keymap.py:6-28`).

## 13. Signature screens

RESEARCH (Experiment #042: hypothesis, PIT dataset, universe, period, baseline vs
candidate, walk-forward bar, IC/ICIR/Sharpe/cost-adj/DD, STATUS: VALIDATED —
wire `ResearchVM.ic/icir` + orphaned `charts/research_plot.rs:103-115`).
MODEL REGISTRY (version/status/OOS + drill into training/features/arch/
validation/drift/calibration/latency). Consensus matrix
(Alpha BUY / Regime BEAR / News NEUTRAL / Risk HIGH / Portfolio REDUCE →
CONSENSUS: CONFLICTED → ACTION: REVIEW — consume `model_disagreement`).
Why-drilldown on any key number (VaR → NVDA 38% / corr 0.81 / vol↑ / HIGH-VOL /
event ELEVATED — evidence, not chain-of-thought).

## 14. `/doctor`, `/status`, sessions

`/doctor`: 14 probes PASS/WARN (data, PIT, features, registry, alpha, risk,
portfolio, firewall, OMS, news-latency, broker, audit, CUDA, storage) →
`HEALTHY WITH 1 WARNING`. Promote from stub (`registry.py:69`).
`/status`: runtime, data, news, portfolio, risk, model, regime, broker, orders,
MCP 4/5, GPU, p99. Sessions `/sessions /new /resume /fork /timeline /export`
(unify singular/plural mismatch) persisting portfolio/research/universe/model/
experiment/risk/watchlist (`session_tabs.py` pointers + SQLite survival).

## 15. Keys

Leader `Ctrl+X`; `Ctrl+P` palette; `Ctrl+M` model; `Ctrl+A` agent; `Ctrl+R`
research; `Ctrl+Shift+R` risk; `Ctrl+O` orders; `Ctrl+L` logs; `Ctrl+N` new;
`Ctrl+S` export; `Esc` close. `1..0` → 12 screens. Kill: `Ctrl+X K` then
`/kill CONFIRM`, bypasses LLM, hits governor (`keymap.py:28`); `Ctrl+K` never kills.

## 16. Take / reject from OpenCode

Take: slash commands, autocomplete, palette, model/agent selectors, MCP manager,
sessions, keyboard-first UX, `@`, `!`, overlays, persistent config, compact layout,
status indicators, extensible commands. Reject: coding-agent semantics, Delta as
coding assistant, shell-to-trade, MCP bypassing risk, raw LLM output as truth,
chat-command for everything.

## 17. Build order UI-1→UI-5

UI-1 Foundation: registry convergence + `commands.toml`, parser/autocomplete parity,
keybinds/theme/layout config, persistent status bar, overlay slots.
UI-2 Interaction: `/model /agent /mcp /sessions /@ /! /help /status /doctor`.
UI-3 Screens: 12 + HOME 4-pane. UI-4 Intelligence: evidence/consensus/Why/
registry/research-viz. UI-5 Polish: latency, resize tiers, mouse, a11y
(`delta_tui/a11y.py`), crash recovery, persistence, offline/safe, export, audit.

End state: "An AI-native quantitative terminal where every command, model, agent,
dataset, experiment, risk decision, and execution state is reachable through one
keyboard-first, evidence-grounded interface."
