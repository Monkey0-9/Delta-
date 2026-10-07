# EXECUTION ARCHITECTURE v1.0 (2026-10-07) — Status: PAPER-READY, LIVE-GATED

OMS: CREATED→VALIDATED→RISK_APPROVED→SUBMITTED→ACK→FILLED (+CANCELLED/REJECTED),
MMap write-ahead journal, kill-9 → replay → snapshot → broker-poll → 3-way reconcile.
RTO<60s RPO=0. Idempotency: client_order_id + idempotency_key, duplicates rejected.
SOR on expected shortfall (spread/fee/rebate/depth/queue/fill-prob/latency/toxicity/health).
FIX: logon/heartbeat/resend/seq-reset/reject/logout/gap-recovery/replay/TLS/drop-copy.
Live adapters (IBKR/FIX) = refusal stubs until R10. TCA: model vs realized → cost calibration.
