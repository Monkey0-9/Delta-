from __future__ import annotations

SCHEMA_VERSION = 1

QUOTE_FIELDS = ("instrument_id", "bid", "ask", "event_time", "received_time", "source", "schema_version")
TRADE_FIELDS = ("instrument_id", "price", "quantity", "event_time", "received_time", "source", "schema_version")
BAR_FIELDS = ("instrument_id", "open", "high", "low", "close", "volume", "event_time", "received_time")
FORECAST_FIELDS = ("instrument_id", "horizon", "expected_return", "risk", "confidence", "model_version", "feature_version")
ORDER_FIELDS = ("order_id", "idempotency_key", "decision_id", "risk_decision_id")
FILL_FIELDS = ("fill_id", "order_id", "quantity", "price", "executed_at")

# W45 additive contracts: PIT quadrangle + multi-asset manifest (no breaking change).
PIT_FIELDS = ("event_id", "event_time", "received_time", "published_time", "effective_time", "source", "payload")
PIT_RULE = "research may only see effective_time <= decision_time"
MANIFEST_FIELDS = ("schema", "experiment_id", "universe", "strategy", "start", "end", "windows", "code_commit", "dataset_hash")
RESEARCH_MANIFEST_SCHEMA = "delta.research_manifest.v1"
SUPPORTED_UNIVERSES = ("SP500", "EQUITY_US", "ETF_US", "BONDS_CORP", "TREASURY", "MACRO_FX")
SUPPORTED_STRATEGIES = ("momentum", "mean_reversion", "value", "quality", "carry")
