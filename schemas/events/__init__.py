from __future__ import annotations

EVENT_SCHEMAS: dict[str, tuple[str, ...]] = {
    "quote": ("event_id", "event_time", "received_time", "source", "schema_version"),
    "trade": ("event_id", "event_time", "received_time", "source", "schema_version"),
    "world_state": ("state_id", "version", "timestamp", "hash"),
    "decision": ("decision_id", "model_version", "strategy_version", "world_state_version"),
    "risk_decision": ("risk_decision_id", "limits_version", "decision_id"),
    "order": ("order_id", "idempotency_key", "decision_id", "risk_decision_id"),
    "fill": ("fill_id", "order_id", "executed_at"),
}
