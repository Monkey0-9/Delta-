# DELTA OS — SRE Runbook (B9)

Every rule below is produced by `observability/ops_rules.py` and evaluated by
`scripts/sre_check.py` (`python scripts/sre_check.py --workdir artifacts/sre`).
Artifact: `artifacts/sre/sre.json` (hash-chained). Scrape: Prometheus
`observability/exporter.py` on `:9108/metrics` (`delta_*` series).

Blindness policy: a rule whose metric is absent does NOT fire — the check
records a `blindness_notes` entry instead. Absent data is never a fabricated
zero, and never a silent page either: investigate blindness like an alert.

Baseline note: thresholds guard against regression from MEASURED numbers
(firewall p50 ~163µs/p99 ~343µs on 2026-10-09, artifacts/bench/bench.json),
not the unmet 7µs P0-plan target (recorded as bench FAIL). Retire this note
only when the bench artifact shows the plan target met.

| Rule | Severity | Meaning | Action | Owner |
| :--- | :---: | :--- | :--- | :--- |
| `kill-switch-engaged` | critical | Trading halted | Do NOT unlock to clear the alert. Diagnose, resolve, then token + RISK_OFFICER+ unlock | risk-officer |
| `risk-latency-p99-hot` | warning | Firewall p99 > 700µs (~2x measured baseline) | Check host load; sustained breach → perf ticket + bench artifact | engineering |
| `risk-latency-p99-critical` | critical | Firewall p99 > 1.4ms (~4x baseline) | Engage kill switch (panic path needs no role), then diagnose | risk-officer |
| `reject-rate-high` | warning | > 5% orders rejected | Read reject reasons in audit ledger; check limits + feed freshness | quant |
| `fill-ratio-low` | warning | Fills < 50% submitted | Compare paper vs broker reports; DR drill if state suspect | operations |
| `sequence-gaps` | warning | Data sequence gaps seen | Data suspect: PIT gates block decisions; verify feed before promoting signals | operations |
| `queue-depth-high` | warning | Queue > 10k backlog | Check exporter/TUI lag; shed non-critical load | engineering |
| `drawdown-breach` | critical | Day drawdown < −2% | Sentinel should hold HALTED; confirm, then review positions | risk-officer |

Escalation (detection-only today): any `critical` SHOULD page risk-officer,
but paging is NOT wired — contacts in `observability/alert_rules.yml` are
`PLACEHOLDER` values, `sre_check` loads them and discards them (no sender),
and the engine is stateless across runs, so the "two `warning` on the same
metric within 15 min → treat as `critical`" rule cannot fire yet either.
GAP (tracked): real paging + escalation state are deferred work; until then
a human reads `artifacts/sre/sre.json` (`blindness_notes` included) on every
WARN/ALERT. Do not claim on-call coverage.
Sign-off matrix (`artifacts/signoff/matrix.md`, B10-owned via
`scripts/signoff.py` — aspirational until that flow is adopted): stays
NO-GO-LIVE while any check is ALERT without a recorded resolution.
