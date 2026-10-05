# DELTA Java Execution Plane — Process Supervision & Failure Domains

## 1. Process Supervision Model (ARCH + SRE)
- **Lifecycle Owner**: `JavaGatewayAdapter` (Python child process supervisor) or OS systemd / Windows Service wrapper.
- **Daemon Binary**: `delta.execution.DeltaJavaGatewayServer` running under OpenJDK 25 LTS.
- **Port Allocation**: Default port `8999` (production paper) or dynamic ports (`9000-9100` for test sandboxes).
- **Restart Policy**:
  - Max 3 consecutive restart attempts with exponential backoff (0.5s, 1.0s, 2.0s).
  - Flap detection: if process terminates within 5 seconds of boot 3 times, fail closed and mark lane `HALTED`.
- **PID Ownership**: Subprocess PID tracked in memory and optional pidfile `~/.delta/run/java_gateway.pid`.

---

## 2. Failure-Domain Boundaries (ARCH)
**Absolute Invariant**: A failure in the Java Execution Plane must never take down the Rust TUI or Python Quantitative Runtime.

- **Crash / SIGKILL**: If Java terminates abruptly:
  - Python bridge catches socket disconnection (`ConnectionResetError` / `BrokenPipeError`).
  - Active orders in flight are marked `PENDING_RECONCILE`.
  - Lane status transitions to `DEGRADED` or `JAVA_UNAVAILABLE`.
  - TUI displays honest `[UNAVAILABLE]` provenance badge.
  - Emergency Kill Switch path operates completely out-of-band via Python in-memory circuit breakers.
- **Hang / Deadlock**: Client enforces a strict 1000ms TCP socket timeout. On timeout, client severs connection and alerts SRE.

---

## 3. Data-Ownership Map (ARCH)

| Domain Object | Authoritative Owner | Java Permissions |
| :--- | :--- | :--- |
| **Security Master & Tickers** | Python / Rust | READ-ONLY (Java receives resolved canonical symbols) |
| **Market Quotes & OHLCV** | Python `DataRouter` | READ-ONLY (Java never fetches from external APIs) |
| **Portfolio NAV & Cash Ledger** | Python Canonical Ledger | WRITE-PROHIBITED (Fills feed Python for accounting) |
| **Risk Limits & VaR Thresholds** | Python Risk Firewall | AUTHORITATIVE PASS/FAIL (Java cannot override) |
| **Order Book Queue & Depths** | Java `OrderBook` | AUTHORITATIVE FOR MATCHING (Paper execution only) |
| **Execution Reports** | Java `FixEngine` | PRODUCER (Serialized and streamed to Python OMS) |

---

## 4. Explicit Non-Goals (ARCH)
- **No User Interface**: Zero UI code in Java (all screens, widgets, and user prompts reside in Rust Ratatui).
- **No Alpha / Quant Logic**: Alphas, regressions, regimes, and models reside in Python / Rust.
- **No Risk Authority**: Java is an execution worker only. It cannot alter risk limits or unlock trading.
