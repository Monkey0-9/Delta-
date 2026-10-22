# DELTA CLI: OpenCode-Parity Audit and Completion Specification

**Audit date:** 22 October 2026  
**Repository reviewed:** Monkey0-9/Delta-  
**Reviewed main revision:** 2508f0d217c50ff34acef5da70afe4e5efab56ef  
**Status:** Engineering audit and delivery specification; not a live-trading certification.

## 1. Executive verdict

DELTA has meaningful foundations: a native Rust/Ratatui terminal, a Python quant and data backend, multiple model/provider paths, market-data adapters, a paper broker, risk and kill-switch components, a command-line package, news and indicator commands, and research/backtest modules. That does not yet make it an OpenCode-equivalent CLI or an institutionally deployable autonomous-trading platform.

The blocking issue is not a lack of commands. The commands, entry points, registries and execution paths do not yet behave as one coherent product. The same user action may enter through Typer, the Python REPL, an older OpenCode-style terminal, the Rust command registry, the Textual fallback or the bridge. Some routes are full operations, some are plans, some list declarations, and some only navigate to a screen. That difference must be visible to the user and enforceable by code—not inferred from a command's name or an attractive status screen.

This audit produced targeted fixes on branch **audit/cli-truth-opencode-parity**:
- model doctor no longer says the platform is ready merely because the local PyTorch/CUDA probe completed; it explicitly says inference is not verified, handles missing PyTorch, and returns a meaningful process result;
- the CLI status command now uses current runtime status instead of a frozen historical baseline;
- bridge dispatch reports BLOCKED, ERROR, unknown-command, unavailable, halted and invalid-input outcomes rather than calling every response successful;
- the Python-to-Rust state payload now uses contract-compatible values for broker connectivity, the model catalogue and kill-switch presence; the Rust contract carries unknown broker connectivity as optional rather than pretending it is false;
- regression tests were added for these contracts.

Those changes have been committed to the audit branch, not main. They have not been run in a local checkout in this environment. CI must validate the branch before any change is merged.

**Current release decision: PAPER / research development only. LIVE trading remains NO-GO.** No CLI, agent, model or market-data connection should be able to override that gate just by selecting a mode, passing a flag, or asking an LLM to do so.

## 2. Evidence and limits of this audit

The source inspection covered the CLI entry point and command application, Python REPL, legacy OpenCode-style terminal, bridge implementation, typed Rust bridge protocol/client/state application, Rust views and command registry, Python command bus, data router, broker adapters, risk and authorization, learning/promotion paths, capability/scope/release documents and selected regression tests. The OpenCode comparison used its current CLI source tree at the observed upstream revision and official documentation linked in Section 5.

This was a targeted repository-level source audit, not a claim that every line of 1,211 tracked files was independently reviewed, that a 300–400 person team audited it, or that the code was executed against real brokers and data. The local session did not have a checked-out source tree, real provider secrets, brokerage account, isolated performance host, GPU weights or production alert channel. Those require CI and controlled environment evidence. Any item marked “not verified” must remain unverified until the corresponding test or operational evidence exists.

Main's last visible source revision for this audit is 11 October 2026. The previously observed main workflows were green: delta-ci #66, Rust Wheels #55 and delta-security-gates #11. Those are useful baseline evidence, not certification of the proposed branch or production readiness.

## 3. What currently exists—and what it actually means

| Surface | Existing foundation | What it does not establish |
|---|---|---|
| Package / startup | The delta entry point prefers the native Rust terminal, then a Textual fallback, then another Python OpenCode-style terminal; named subcommands use Typer. | One consistent runtime, identical command behavior, one permission model or one tested command contract across all paths. |
| Native terminal | Ratatui/Crossterm screens include market, candlestick, research, portfolio, risk, orders, model, agent and system views. | That every panel has authoritative, fresh, correctly typed broker/data/model state. |
| Python interactive commands | The REPL includes commands for models, MCP, tools, auth/keys, news, macro, data, indicators, broker, risk, portfolio, trading, learning, automation and status. | That every command is wired to a live implementation; some responses are declarations, best-effort output, simulation or manual workflow. |
| Typer CLI | About 15 named commands include doctor, status, research, scan, portfolio-review, watch, learn and promote. | That “research” means a completed backtest, “watch” means a 24/7 daemon, “learn” retrains a model, or “promote” validates evidence independently. |
| Command bus | Typed request/response/event/error concepts exist in core/command_bus.py. | Production canonical dispatch: registry handlers commonly return SCREEN navigation results and do not share the same functional command path as the REPL/bridge. |
| Data and market information | yfinance and Yahoo REST paths, a labeled stale cache, synthetic simulation fallback, FRED and Google News RSS paths, plus indicators. | Institutional consolidated market data, exchange-grade tick/order-book data, fully point-in-time news, licensed redistribution, or a validated predictive news signal. |
| Broker adapters | Paper ledger; Alpaca paper adapter; explicitly incomplete IBKR/session path. | Verified production connection, cross-process exactly-once order submission, testnet session recovery and reconciliation parity, or live authorization. |
| Model layer | Provider catalogue/gateway/router paths, a local Ollama route in the trader runtime, finance policy code and specialist agents. | That every listed model works, has valid credentials/weights, completes inference, is calibrated, or has predictive trading edge. |
| Risk | Pre-trade firewall, kill-switch concepts, limits and risk views exist. | A single tested kill-switch authority across every execution path, authenticated human identity, durable multi-process order idempotency, or validated risk controls under real broker failure. |
| Learning | Outcome/experience and lesson abstractions exist. | Durable CLI outcome history, safe automatic training, verified improvement, or production model promotion. |
| Monitoring | A watch evaluator and health/status abstractions exist. | A persistent service, watchdog, paging delivery, on-call coverage, automatic recovery or 24/7 operational commitment. |

### P0: bridge status and state must be truthful

The original Python bridge returned status “ok” for every non-empty terminal response. The Rust client uses that value as its success indicator. A blocked trade, invalid command, unavailable feed or runtime error could therefore be painted as a successful dispatch. The audit branch now classifies explicit result prefixes and makes the Rust UI treat a confirmed “halted” result as an expected safety success, while retaining failure status for blocked/error/unknown outcomes.

A separate schema issue was also confirmed: Python returned strings such as “UNAVAILABLE” for Rust boolean fields and a string for a Rust vector of available model names. Rust's typed deserializer rejects those mismatched types; the client quietly ignores the failed StateSnapshot parse. The branch changes broker connectivity to optional bool, uses a boolean for switch availability, returns a model-name array from the local catalogue, includes provenance, and adds a Rust JSON-deserialization regression test. Model health intentionally stays UNAVAILABLE until a real inference probe succeeds.

These are not cosmetic fixes. State contract tests must become a mandatory gate for every bridge change.

## 4. Root architectural correction: one execution API

DELTA needs one command/service layer used by Rust UI actions, Typer, scripts and the REPL compatibility shim. Do not add a fifth command frontend.

Recommended flow:

1. **Clients:** native Ratatui TUI, Typer CLI, scripts/CI and optional remote control client.
2. **Protocol boundary:** versioned typed request, correlation ID, authenticated principal, workspace, deadline, idempotency key, arguments validated against a schema, requested mode and approval token where relevant.
3. **Canonical command registry:** stable command IDs, argument/result schemas, permission requirements, side-effect class, deadline, idempotency behavior, output type, evidence/provenance contract and owner.
4. **Application services:** research, data, market/news, portfolio, risk, models, tools/MCP, broker/OMS, monitoring and learning.
5. **Domain adapters:** market-data feeds, news sources, model providers, MCP processes, broker API and paper simulator.
6. **Durable audit/event ledger:** request, principal, inputs/hash, tool/provider versions, data lineage, decision, risk verdict, approvals, broker acknowledgement, fills, reconciliation, model version and timestamps.
7. **Typed response:** success, partial, pending, blocked, unavailable, cancelled, invalid input or error; include user-safe message, evidence/provenance and remediation hint. “A command returned text” must not equal “the command succeeded.”

Navigation commands must be separate from financial/execution commands. A registry item that returns SCREEN:portfolio is a navigation action, not an executed portfolio operation. Canonical command metadata should generate the Typer help, slash-command help, command palette, permission tests and support docs. Retired aliases should be explicit shims with deprecation dates.

### Canonical command contract

Every command must declare:
- stable ID and versioned input/output schema;
- arguments and bounds, with no implicit trading quantity/capital defaults in execution paths;
- role/capability permissions independent of caller-provided role strings;
- effect classification: read-only, local write, external network, research compute, order proposal, order mutation or emergency stop;
- freshness requirements, data-source requirements and whether synthetic/stale data is permissible;
- idempotency semantics and timeout/cancellation behavior;
- approval class and the exact payload that was approved;
- status enum, structured errors, provenance and audit event;
- deterministic unit/integration tests, negative tests and failure-mode tests.

Standard process behavior should include stable exit codes and explicit output modes: human-readable, JSON and NDJSON. A script must be able to distinguish “blocked by risk,” “no credentials,” “feed stale,” “nothing found,” “command invalid,” “order acknowledged,” “partially filled” and “filled.” Never parse colorful prose to decide whether money moved.

## 5. OpenCode parity: what to emulate, what not to copy

OpenCode's official CLI documentation includes non-interactive runs, session continuation, model and agent selection, machine-readable output, session lifecycle and server options. Its MCP documentation covers local process servers and remote connections, tools and authentication; its skills documentation describes on-demand discovery from project and global SKILL.md locations; its tools and permissions documentation separates tool capability from allow/ask/deny decisions. This gives DELTA useful product reference points.

References:
- OpenCode CLI and command documentation: https://opencode.ai/v2/docs/cli/commands and https://dev.opencode.ai/docs/cli/
- MCP server lifecycle and OAuth: https://docs.opencode.ai/docs/mcp-servers/
- Skills and on-demand discovery: https://docs.opencode.ai/docs/skills/
- Tools and permission policy: https://docs.opencode.ai/docs/tools/ and https://docs.opencode.ai/docs/permissions/
- CLI source snapshot inspected: https://github.com/anomalyco/opencode/tree/e965774fa0e2a8ffb27bf02827a2c3c6a8c0f45b/packages/cli/src/commands

DELTA should match the usability concepts, not blindly copy all permissive behavior. In a quant product, file edits, remote network tools and shell execution need sandboxing and consent; placing an order needs a stricter, payload-bound authorization path. A generic “auto approve everything” or “yolo” flag must never authorize financial orders or bypass the risk firewall.

Parity backlog:
- interactive full-screen TUI and concise/minimal terminal modes;
- non-interactive run command with model, agent, session, file context, deadlines and JSON/NDJSON output;
- sessions: list, show, resume, fork, export, import and redact;
- provider authentication: inspect configured slots, add/remove/test keys and report exact verification state;
- model commands: list, info, capabilities, probe, switch and benchmark;
- MCP commands: add, list, inspect, connect/probe, auth/logout, tools, disable/remove and health;
- skills: list/discover, inspect provenance, load on demand and require review when a skill can trigger side effects;
- tool/plugin registry: source, version, permission, isolation boundary, health, rate-limit and audit trail;
- workspace and config precedence, project/global scope, command help completion and actionable diagnostics;
- traceable command outcomes, cancellation and session continuation;
- offline-safe doctor, packaged runtime, bridge health and protocol compatibility checks.

## 6. Proposed CLI user experience

Keep the Rust terminal as the canonical interactive frontend. The Python Textual UI and legacy OpenCode terminal should be retired or clearly marked as fallback-only once feature parity is proven. Do not build a competing web dashboard; the user explicitly wants charts and research in separate terminal sections.

### Primary terminal sections

| Section | Must show |
|---|---|
| Desk | current environment/mode, connection health, operator, clock/session, top risk alerts, current task and recent audit events. |
| Markets | quotes, sessions/calendar, universe/watchlists, current data provider, freshness and timestamps. |
| Charts | separate native screen for candles, line, OHLC, volume, VWAP, selected indicators, fills/entries/exits, equity and drawdown. |
| Research | datasets, as-of policy, features, strategies, hypotheses, jobs, backtest runs, diagnostics and artifact lineage. |
| Portfolio | actual connected account status, cash, positions, cost basis, open orders, reconciliation status and source timestamps. |
| Risk | limits, exposure, concentration, factor/sector/currency risks, VaR/CVaR, drawdown, stress, borrow/margin where applicable and kill-switch status. |
| Orders / execution | proposed, approved, submitted, accepted, partially filled, filled, cancelled, rejected and unknown states, plus broker reconciliation. |
| Models | catalogue vs configured vs authenticated vs inference-tested vs qualified-for-role; latency, limits, error rate, model version and fallback. |
| Agents / tools | current runs, plan steps, tools requested, approvals, evidence, costs, timeouts and audit events. |
| MCP / skills | declared vs connected servers, discovered tools, permission level, source and version of loaded skill, health and last successful probe. |
| Sessions / workspace | named projects/workspaces, recent runs, continue/fork/export, attached files/datasets and redaction. |
| Automation / system | active services, last heartbeat, queued jobs, alert delivery, clock/data lag, recovery events and runbook links. |

### Chart-section design

A dedicated Markets → Charts screen must support candle/line, volume, VWAP, indicators, portfolio equity and drawdown, research diagnostics and execution overlays. It needs responsive layout tiers for 80-column and wider terminals, keyboard-accessible symbol/timeframe/indicator controls, crosshair or cursor readout, selected date/time, source/freshness badges and clear “not available” states.

Synthetic L2 is not a real order book; never draw it as if it were broker-sourced market depth. Every chart panel should carry source, as-of timestamp, timezone, interval, adjustment policy and data-quality status. Stale or synthetic data must be conspicuously labeled and prohibited from live signals/order gates. When history is missing, show missing history—not a fabricated smooth line.

### Canonical command examples

The exact spelling can evolve, but these user jobs must have stable contracts:

- general: **delta**, **delta --help**, **delta doctor**, **delta status --json**, **delta run --format json**
- sessions: **delta session list/show/resume/fork/export/import**
- models: **delta model list/info/probe/use**
- credentials: **delta auth list/login/logout/test**, with secrets entered through secure prompts or environment/keyring references
- tools: **delta tool list/inspect/probe**, **delta mcp list/add/auth/logout/remove**
- skills: **delta skill list/inspect/load**
- markets: **delta data status**, **delta quote SYMBOL**, **delta news search SYMBOL**, **delta chart SYMBOL --type candle**
- research: **delta research plan**, **delta research run**, **delta backtest**, **delta experiment inspect**, **delta experiment compare**
- portfolio/risk: **delta portfolio status**, **delta risk status**, **delta risk limits**, **delta risk stress**
- execution: **delta order plan**, **delta order preview**, **delta order submit**, **delta order cancel**, **delta reconcile**, with approval generated from the exact reviewed order payload
- operations: **delta monitor status**, **delta automation list/start/stop**, **delta audit export**, **delta kill**.

Never let a read-only command quietly place an order. Never make “start autonomous mode” enough to turn on live execution unless every release gate is independently satisfied.

## 7. Quant platform capability design

### Models and provider integrations

Use one canonical model gateway and catalogue. Each entry must separate provider family, exact model ID, base URL, auth slot, capability claims, observed capabilities, context/response limits, request timeout, cost/rate limits, concurrency, last probe time, last real inference time, latency and failure rate. Provider-specific models must not be “READY” because a name is present or a key exists. The release state ladder should be explicit: DECLARED → CONFIGURED → AUTHENTICATED → INFERENCE_TESTED → QUALIFIED_FOR_TASK → DEGRADED/UNAVAILABLE.

A real health probe performs a bounded, low-cost request with no trading authority and validates a typed response. Local weights must be checksummed and versioned; GPU/device memory compatibility needs a local check. Cloud credentials belong in an OS keyring or encrypted vault (or secret manager for services), not source code, repo config, shell history, logs or terminal transcript. Provide rotation/revocation, provider-level scopes, timeout, backoff, per-provider circuit breaker and safe fallback. Fallback must not silently downgrade a research model or inference result while keeping the same qualification badge.

The present deterministic FinanceAnalysisPolicy and deterministic specialist-agent heuristics are useful guardrails and baselines; they are not themselves a trained predictive model or evidence of alpha. The current synthetic instruction dataset and small grounded examples can support format/grounding experiments, but do not establish forecasting skill or live-trading edge. Full training/evaluation needs immutable data, label definition, split lineage, GPU/weight availability, reproducible training, out-of-sample evaluation, calibration, bias/leakage checks, model card and rollback artefact.

### Tools, MCP, skills and plugins

The current MCP surface contains declared integration names, many unprobed. Implement true MCP lifecycle: local process start/stop, remote transport, protocol handshake, capabilities/tools discovery, authentication/OAuth where needed, health/latency, error handling, output size limits and restart policy. Store configuration per project/user/service without storing secrets in plaintext. Each server and each discovered tool needs separate allow/ask/deny policy.

Every external tool result must include source, timestamps, raw-result digest, normalized representation, status and trust class. Untrusted web/news/tool text is data, never executable instructions. Protect the context boundary from prompt injection. Tool calls that edit workspaces or invoke external side effects need sandbox/approvals. Trading tools must call the same central risk/OMS services as the UI; no agent gets a direct broker handle that can bypass them.

Skills should be versioned instruction packages discovered in project/global paths. Display name, source, version/hash, requested tools and allowed scope before first load. A skill must not elevate the user's permissions. Plugins require allowlisted installation origins, version pinning, integrity/signature policy where available, isolated execution and revocation.

### Market data, news and indicators

Build a provider adapter contract, not more scattered direct HTTP calls. Every record needs instrument/security-master ID, venue, event and receive timestamps, source, adjustment status, timezone, currency, quality flags and freshness. Preserve raw and normalized records, reject duplicate/out-of-order or corrupt bars per policy, version corporate-action adjustments and build explicit PIT snapshots. Data failures should be visible and fail closed for signal/trading paths.

News must store publisher/source, published time, fetched time, symbol/entity mapping confidence, content hash, duplicate cluster, licensing/access class and provenance. Keyword sentiment is a heuristic, not an institutional news alpha model. Validate entity relevance, stale/revised articles, language, source reliability and prompt-injection attacks. Backtests must use only information available at the decision timestamp. If source or time is unknown, do not backdate it.

Technical indicators can be exposed as research tools, but define warm-up length, missing values, price adjustment, look-ahead rules and indicator version. An indicator is not a forecast. Every signal needs a hypothesis, expected horizon, benchmark, costs, rejection/abstain rule and attribution.

### Research and validation

A real research run must have immutable inputs and reproducible outputs: dataset/snapshot ID and hash, security universe and delisted names, PIT policy, feature/label versions, strategy revision, parameters, code commit, dependency lock, seeds, dates, benchmark, transaction-cost/borrow assumptions, output artifact hashes and diagnostics. “Plan registered” must appear as PLAN, not COMPLETED BACKTEST.

Mandatory gates include walk-forward and out-of-sample splits with leakage checks, multiple-testing correction, transaction costs/slippage/market impact, turnover/capacity, realistic fills, limit/up/down days and halts where applicable, stress/regime slices, bootstrap/uncertainty estimates, sensitivity and benchmark comparison. A strategy is not promoted because an operator passes boolean CLI flags. Promotion must independently read signed evidence artifacts and validate hashes, sample sizes, gates and approvals.

### Portfolios, risk and broker/OMS

A portfolio screen may label only data from a probed account as authoritative. Default account/capital labels must not make a simulated USD 1m book look like a real portfolio. Separate configured mandate capital, paper-ledger equity, external broker account equity and unavailable states. Reconcile orders, executions, cash, positions and fees with broker evidence. Any unknown/rejected/pending state blocks additional risk-increasing submission until reconciled.

The kill path needs a shared authoritative state, independent from model confidence and all AI decisions. Global/strategy/broker halts must propagate to every submit route. Unlock must require authenticated identity, short-lived authorization, reason, role, strong audit event and, for production, dual control where appropriate. A CLI “--yes” flag or caller-supplied role string is not sufficient authority. Bind approval to exact symbol, side, quantity, limit/market type, venue, account, time-in-force, price bounds, mandate/risk context and expiry; any payload mutation invalidates approval.

Pre-trade controls should cover per-order/notional limits, position and portfolio limits, gross/net exposure, leverage, concentration, sector/factor/currency limits, liquidity/participation, price collars, stale/crossed data, market sessions, volatility, loss/drawdown, VaR/CVaR/stress where supportable, borrow/short locate, margin and duplicate submissions. Show which limit blocked an order and the configured source/version. Do not claim unsupported options/futures/FX/rates coverage until their full product mechanics and risk are implemented.

Broker adapters must have contract tests for connect/auth, account snapshot, order submit/ack, idempotency, partial/full fill, cancel race, disconnect/reconnect, duplicate/missing/out-of-order messages, restart recovery and reconciliation. Test on sandbox/testnet and paper first. LIVE must remain hard-gated until adapter-specific parity and recovery evidence is archived.

### Monitoring and learning

A 24/7 monitor is a deployed service, not a one-shot CLI function. Build a supervised process with heartbeat, dead-man switch, persistent job/state store, bounded retry, watchdog, health endpoint/CLI, alert delivery, on-call rotation, recovery and escalation runbooks. Demonstrate an actual test page and acknowledgement; a configured email/phone placeholder is not a successful alert. Measure lag, queue depth, stale feed duration, model timeout/error rate, order acknowledgements, reconciliation drift, reject rate, fill/cancel timing, risk breaches and process restart loops. Run a controlled multi-day shadow/soak before release.

“Self-learning” must be an auditable offline promotion loop: collect outcomes → attribute model/data/tool/risk/trader cause → propose lesson → add a versioned test/counterexample → replay regression corpus → train/evaluate candidate offline → run OOS/calibration/security checks → obtain approval → canary/shadow → promote/rollback. A single losing trade must not retrain an active model or increase risk. Risk policies, limits and the kill switch cannot be modified by self-learning agents. Persist the experience ledger; record nothing as learned if the write failed.

## 8. Weighted CLI completion plan (100 points)

These weights express engineering effort/importance, not a claimed score of current completion.

| Workstream | Weight | Completion evidence |
|---|---:|---|
| Canonical command runtime and bridge contracts | 16 | One registry/runtime; typed request/results; all Python/Rust/CLI contracts tested; no “all statuses ok”; compatibility/version tests. |
| Rust TUI workflow and navigation | 8 | Native canonical screen flows; same service operations as CLI; resize/keybinding/a11y tests; no hidden fallback behavior. |
| Models, providers and credentials | 10 | Catalogue/configured/authenticated/probed states; local model inference and each declared cloud provider tested; vault/rotation/redaction tests. |
| Data, news, indicators and charts | 10 | Source/freshness/PIT metadata; adapter contract tests; synthetic/stale warning tests; charts clearly labeled, correct timezone and no invented depth. |
| Research, backtesting and statistics | 13 | Immutable experiment manifest; executable research/backtest; look-ahead/leakage tests; cost/impact/OOS/walk-forward and correction report. |
| Portfolio, risk allocation and controls | 14 | Authoritative portfolio read; shared hard limits; independent kill; fail-closed, auth/approval tests; broker/portfolio reconciliation. |
| Broker and OMS lifecycle | 13 | Paper + supported sandbox adapters; ack/fill/cancel/reconnect/restart tests; idempotency under concurrent processes; LIVE gate remains unoverrideable. |
| Agents, tools, MCP, skills and plugins | 6 | Real discovery/probes; allowlists, sandbox, timeout and scope tests; no privilege escalation; full tool provenance. |
| Automation, monitoring and SRE | 5 | Persistent daemon, heartbeat, alert delivery and acknowledgement proof, restart/failover, runbook and soak evidence. |
| Learning, audit and reproducibility | 5 | Durable outcome store, causal attribution, regression tests, offline model promotion artifacts, rollback and signoff trail. |
| **Total** | **100** | Release readiness is based on evidence per row, not subjective polish. |

### Delivery order

**P0 — trust and state correctness.** Fix schema/result status mismatches; add bridge contract and Rust deserialization tests; make doctor/status/command exit status truthful; prove paper ledger state and kill path; prohibit LIVE mode from bypassing the central release gate. Complete this before adding new agent tools.

**P1 — single command runtime.** Create canonical command metadata and application services. Convert legacy interfaces into clients/shims. Generate help, completion, CLI slash commands and command-palette metadata from the same registry. Add JSON/NDJSON output, exit code standards, structured errors, cancellation/deadlines and persistent sessions. Retire duplicate dispatch paths only after parity tests pass.

**P2 — provider and research workflows.** Implement real model/provider inference probes and key lifecycle, MCP start/auth/discovery, tools/skills permissioning, data/news provenance, the separate chart section and reproducible research jobs. Label every path not yet production-verified as such.

**P3 — portfolio, OMS and risk controls.** Use actual adapter-sourced account data, persistent orders and fills, exact payload approval, idempotency across processes, reconnect/recovery and order/position/cash reconciliation. Expand asset scope only after product mechanics, risk and testnet evidence are complete.

**P4 — durable learning and operations.** Durable outcomes and experiment registry, offline candidate evaluation/promotion/rollback, 24/7 service deployment, real alert paging, recovery drills, security testing, hardware benchmarks and a multi-day shadow/soak. Then require all independent sign-offs.

## 9. Definition of done / mandatory release gates

A command is “implemented” only if there is an owner, contract, unit tests, positive/negative integration tests, typed result, meaningful errors, permission rules, audit event, and a working help example. Network and broker commands must have timeouts, fault injection and replayable tests. CLI help must say PLAN, SIMULATION, PAPER, UNAVAILABLE, DEGRADED or LIVE clearly; labels come from measured state.

Paper-release requirements:
- current all-green Python and Rust CI on the release candidate;
- bridge schema compatibility test and Rust deserialization test;
- offline startup and missing-key/provider behavior tested;
- synthetic and stale data cannot reach production research/promotion/order paths;
- deterministic paper broker + order lifecycle/restart/reconcile tests;
- kill and cancellation work under load and while providers/timeouts fail;
- docs/capability register agree with implementation and current workflow artifacts.

Shadow-live requirements:
- real read-only adapter connection with permissions limited to account/market reads;
- live market-data quality/freshness and exchange calendar verified for each intended venue;
- full paper/real snapshot consistency and reconciliation;
- event capture, 14-day soak (or approved duration with justification), restart recovery and no silent data loss;
- alert delivery tested with named, staffed on-call coverage;
- security review, secrets scan, dependency audit, DAST and external/independent review.

Live-trading requirements:
- supported asset/venue/product and legal/regulatory applicability independently approved for the actual operating entity/jurisdictions;
- broker-specific testnet certification covering partial fills, cancel races, session recovery and exactly-once behavior under process death;
- signed walk-forward/OOS/stress/capacity/cost-calibration artifacts, approved thresholds and risk limits;
- enforceable authenticated operator identity, short-lived credentials, dual control where policy requires and payload-bound approvals;
- risk officer, quant/research owner, broker/OMS owner, security, SRE/on-call and release owner sign-offs;
- kill, flatten/cancel policy, restart, reconciliation and rollback drill demonstrated on the production-equivalent environment;
- no critical/high findings open, no unreviewed model/data/command paths, no implicit live enable from configuration flags;
- a release controller that evaluates actual evidence and cannot be bypassed by caller-supplied boolean flags.

No system can guarantee zero surprises. The disciplined goal is zero known unmitigated critical failure modes, safe failure for unknown conditions, small initial limits, observable decisions, immediate halt, and verified recovery.

## 10. Asset scope and governance

The current scope register says equities are supported within the paper-only boundary; options/futures are analytics-only; FX/rates are unsupported; portfolio attribution is unsupported; market regimes remain experimental; alternative data and strategy capacity are partial. Preserve this scope. Options and futures require complete contract terms, expiry, exercise/assignment, margin, settlements and rolls. FX/rates require conventions, calendars, curves, funding and cross-asset risk. Attribution requires benchmarks and factor exposures. Capacity needs borrow, crowding, fill-calibrated liquidity/capacity degradation curves. A broad “we support all markets” UI label is unacceptable.

Regulatory mappings are jurisdiction- and business-model-specific. For US broker-dealer market access, review the applicable SEC market-access controls and legal interpretation: https://www.sec.gov/rules-regulations/2011/06/risk-management-controls-brokers-or-dealers-market-access. For EU firms within scope, review MiFID II Article 17 algorithmic trading obligations with qualified counsel: https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mifid-ii/article-17-algorithmic-trading. These are reference points, not a claim that DELTA is certified or that either law universally applies.

## 11. Documents and registers that must be reconciled

Use one machine-readable release manifest to generate STATUS.md, SUPPORTED_SCOPE.yaml, CAPABILITY_REGISTER.yaml, RELEASE_GATES.md and operator runbooks. The current documents have drift:
- security gate entry still says a first blocking run is needed although a later green run is recorded;
- tick/PIT lineage limitations differ from newer status notes;
- cost calibration and forecast-calibration entries differ from the latest v2.8 status, while event-driven fill-dependent promotion remains open;
- old FIX/IBKR/performance statements conflict with newer source and measured SRE numbers;
- generic mode config permits broker-order flags while release documentation says live remains gated.

Each capability should use explicit states such as DECLARED, IMPLEMENTED, TESTED, VALIDATED, SHADOWED, RELEASED, DEGRADED, RETIRED. Attach commit, CI run, artifact, test command, date, environment and signer. If evidence is stale, it does not qualify.

## 12. First PR acceptance checklist

This audit branch should not merge until CI has:
- passed the new Python model-doctor, runtime-status, bridge-status and bridge-state contract tests;
- passed Rust compilation and integration tests after the bridge protocol type change;
- passed all existing Python/Rust/security CI suites;
- shown a typed StateSnapshot can be deserialized from a payload matching the Python bridge;
- confirmed a blocked/error/unknown command is not rendered as successful and a confirmed kill is not shown as an ordinary failure;
- reviewed the new contract for backward compatibility and validated no caller can override LIVE release state.

After that PR, execute P1 and P2 as separately reviewed increments, not as one large rewrite. Keep the native terminal canonical and preserve every existing kill/risk invariant during the migration.
