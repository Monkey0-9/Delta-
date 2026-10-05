# DELTA Java Execution Plane — Wire Contract Specification

**Contract Version**: `1.0.0`  
**Status**: FROZEN  
**Transport**: TCP Socket / Loopback IPC (Default Port: `8999` or dynamic)  
**Encoding**: UTF-8, newline (`\n`) delimited framing  

---

## 1. Versioning Policy & Compatibility Window
- **SemVer Compliance**: `MAJOR.MINOR.PATCH`
  - `MAJOR`: Breaking payload schema changes, field removals, or semantic state transitions. Requires coordinated client/server upgrade.
  - `MINOR`: New additive methods or optional telemetry fields. Backward compatible within same `MAJOR`.
  - `PATCH`: Internal bug fixes, latency optimizations, or non-functional refactors.
- **Handshake Gate**: During connection initialization, client must issue `VERSION` and verify server contract version `MAJOR` matches.
- **Break Procedure**: Any breaking wire change requires:
  1. Deprecation notice in `docs/adr/`.
  2. 60-day compatibility bridge or explicit version negotiation.
  3. Hard fail-closed on version mismatch (`ERR_VERSION_MISMATCH`).

---

## 2. Protocol Methods & Wire Schemas

### 2.1 PING (Liveness Probe)
- **Request**:
  ```text
  PING\n
  ```
- **Response**:
  ```text
  PONG\n
  ```

### 2.2 MATCH (Order Submission & Matching Execution)
Submits a validated order into the Disruptor ring buffer and order book matching engine.
- **Request**:
  ```text
  MATCH <clOrdId> <symbol> <side> <type> <priceTicks> <quantity>\n
  ```
  - `clOrdId`: String (unique client order ID, e.g., `ORD-2026-001`)
  - `symbol`: String (uppercase security identifier, e.g., `NVDA`)
  - `side`: `BUY` | `SELL`
  - `type`: `MKT` | `LMT`
  - `priceTicks`: Integer ticks (cents, e.g. `$185.00` = `18500`)
  - `quantity`: Integer (shares/contracts)
- **Response**:
  ```text
  MATCH_OK <report_count>\n
  <clOrdId>,<symbol>,<side>,<fillQty>,<cumQty>,<priceTicks>,<execType>,<fixReport>\n
  ... (repeated for each execution report)
  ```
  - `execType`: `0` (New ACK), `1` (Partial Fill), `2` (Full Fill), `4` (Canceled), `8` (Rejected)
  - `fixReport`: Standard FIX 4.2 delimited tag=value string (`8=FIX.4.2|...|10=XYZ|`)

### 2.3 CANCEL (Order Cancellation)
Requests cancellation of a resting limit order in the book.
- **Request**:
  ```text
  CANCEL <symbol> <clOrdId>\n
  ```
- **Response**:
  - Success: `CANCEL_OK\n`
  - Failure/Not Found: `CANCEL_REJECT\n`

### 2.4 STATUS (Introspection & Health Telemetry)
Queries gateway telemetry, ring depth, and sequence cursors.
- **Request**:
  ```text
  STATUS\n
  ```
- **Response**:
  ```text
  STATUS_OK <ring_depth> <cursor> <uptime_ms> <active_symbols>\n
  ```

---

## 3. Error Codes & Failure Semantics
All protocol errors follow the format:
```text
ERR <ERROR_CODE> [OPTIONAL_REASON]\n
```

| Error Code | Meaning | Handling Action |
| :--- | :--- | :--- |
| `ERR_UNKNOWN_COMMAND` | Method verb not recognized by gateway | Client logs error; fails closed |
| `ERR_INVALID_ARGUMENT` | Malformed parameters or unparseable numbers | Order rejected; error surfaced to OMS |
| `ERR_BUFFER_OVERFLOW` | Disruptor ring buffer saturated | Backpressure triggered; OMS drops or queues |
| `ERR_VERSION_MISMATCH` | Contract semver mismatch | Process halted; alerts raised |
| `ERR_LIVE_PROHIBITED` | Order attempted with live flag | Hard security block; audit event fired |
