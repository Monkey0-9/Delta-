# SECURITY / OFFLINE / ROLLBACK (Stage-5 Z+.3) — v1.0 2026-10-07

Vault: core/vault.py AES-256-GCM done. Added here:
- Rotation: keys rotate via vault re-wrap; old key retained one cycle for replay.
- RBAC: roles RESEARCHER/QUANT/RISK_OFFICER/OPERATOR/ADMIN; kill/unlock = RISK_OFFICER+.
  Beyond DELTA_UNLOCK_TOKEN: kill board binds GLOBAL/strategy/broker (one board).
- Prompt-injection suite: data/news/trust.py regex + quarantine; LLM output never
  reaches OMS (authority gate tested).
- Secrets masking: security/redaction.py masks keys in logs/audit.
- Provider fallback / offline mode: MARKET-DATA providers ordered live→cache→synthetic
  with explicit SOURCE badges; offline = cache-or-UNAVAILABLE, never fake-live.
  Kill-switch works offline (in-memory, no network hop).
- Update rollback: registry demote/retire + reproduce(EXP-ID); binary deploys keep
  prior version + manifest hash; rollback = redeploy prior hash, replay OMS journal.
- Drill: kill-switch monthly, logged with receipt.
