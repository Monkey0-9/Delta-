from enum import StrEnum


class EventType(StrEnum):
    MARKET_TICK = "market_tick"
    MARKET_BAR = "market_bar"
    QUOTE = "quote"
    TRADE = "trade"

    NEWS = "news"
    MACRO_UPDATE = "macro_update"
    REGIME_CHANGE = "regime_change"

    DECISION_CREATED = "decision_created"

    RISK_CHECK_REQUESTED = "risk_check_requested"
    RISK_APPROVED = "risk_approved"
    RISK_REJECTED = "risk_rejected"

    ORDER_INTENT_CREATED = "order_intent_created"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_ACCEPTED = "order_accepted"

    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"

    PORTFOLIO_UPDATED = "portfolio_updated"

    SYSTEM_ALERT = "system_alert"
    KILL_SWITCH = "kill_switch"