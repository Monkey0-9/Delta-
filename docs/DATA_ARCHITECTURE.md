# DATA ARCHITECTURE v1.0 (2026-10-07) — Status: PARTIAL (PIT enforced, labels new)

Layers: raw/ → normalized/ → pit/ → features/ → datasets/.
Canonical record: DataPoint(symbol, event_time, publication_time, received_time,
effective_time, source, revision, dataset_version, quality) — see core/domain/canonical.py.
Guarantee: t_event ≤ t_pub ≤ t_avail ≤ t_dec ≤ t_exec. PIT-join rejects any row
with available_at > decision asof. Information published 15:30 never informs a 15:00 decision.
Quality: DataQualityReport PASS/WARN/FAIL; FAIL raises before training/promotion.
Corp actions: splits/dividends/mergers/spinoffs/symbol-change/delist/rights; applied_at ≥ ex_date.
Snapshots hashed (sha16/256) into experiment manifests; reproduce(EXP-ID) hash-equal.
