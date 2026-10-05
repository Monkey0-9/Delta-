# DELTA Group Gate Verification Checklist Template

This checklist must be satisfied and verified for every group (01 through 30) before promotion to the subsequent group.

---

## Group Gate Requirements

### 1. Code Compilation & Build
- [ ] Java: Clean compilation with zero warnings (`javac --release 25`)
- [ ] Rust: `cargo check --workspace` clean (0 errors, 0 warnings)
- [ ] Rust Tests: `cargo test --workspace --lib` clean (all unit tests passing)

### 2. Automated Test Verification
- [ ] Group Unit Tests: All targeted group tests passing
- [ ] Canonical Regression Suite: `pytest tests/test_canonical_end_to_end.py` (12/12 passing)
- [ ] Redesign Acceptance Suite: `pytest tests/test_terminal_redesign.py` (38/38 passing)

### 3. Truth Over Polish Invariants
- [ ] Zero hardcoded / demo metrics introduced
- [ ] Provenance badges explicit on all telemetry (`LIVE | PAPER | SIM | SYNTHETIC | UNAVAILABLE`)
- [ ] Fail-closed error handling verified

### 4. Documentation & Artifacts
- [ ] Specifications updated
- [ ] Metrics recorded with exact benchmark hardware and sample sizes
- [ ] Commit diff clean and targeted
