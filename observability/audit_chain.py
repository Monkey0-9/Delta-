from __future__ import annotations

from provenance.audit.chain import AuditChain as _CanonicalAuditChain


class AuditChain(_CanonicalAuditChain):
    """Observability alias of the canonical provenance audit chain.

    Single source of truth: provenance.audit.chain.AuditChain.
    Retained for backward-compatible imports.
    """

    @property
    def head(self) -> str:  # type: ignore[override]
        return self.head_hash

    def append(self, event: dict) -> str:  # type: ignore[override]
        import hashlib
        import json

        payload_hash = hashlib.sha256(
            json.dumps(event, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        record = super().append(
            record_type=str(event.get("type", "observability.event")),
            record_id=str(event.get("id", payload_hash[:16])),
            payload_hash=payload_hash,
        )
        return record.record_hash