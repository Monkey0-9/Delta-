from trader.intent import (
    Domain,
    ExecutionMode,
    FinanceIntent,
    Horizon,
    Intent,
    Objective,
)


def test_domain_contract() -> None:
    assert Domain.FINANCE.value == "finance"
    assert Domain.NON_FINANCE.value == "non_finance"
    assert Domain.AMBIGUOUS.value == "ambiguous"


def test_intent_has_safe_unknown_state() -> None:
    assert Intent.UNKNOWN.value == "unknown"


def test_horizon_has_explicit_unspecified_state() -> None:
    assert Horizon.UNSPECIFIED.value == "unspecified"


def test_objective_has_mandate_default() -> None:
    assert Objective.MANDATE_DEFAULT.value == "mandate_default"


def test_default_execution_mode_is_non_executing() -> None:
    intent = FinanceIntent(intent=Intent.TRADE_DECISION)

    assert intent.execution_mode is ExecutionMode.RECOMMENDATION


def test_symbols_are_normalized_and_deduplicated() -> None:
    intent = FinanceIntent(
        intent=Intent.ASSET_ANALYSIS,
        symbols=("aapl", "MSFT", "AAPL", " msft "),
    )

    assert intent.normalized_symbols() == ("AAPL", "MSFT")


def test_unknown_intent_is_not_actionable() -> None:
    intent = FinanceIntent(intent=Intent.UNKNOWN)

    assert intent.is_actionable() is False


def test_recommendation_mode_requires_no_execution_authority() -> None:
    intent = FinanceIntent(
        intent=Intent.TRADE_DECISION,
        execution_mode=ExecutionMode.RECOMMENDATION,
    )

    assert intent.requires_execution_authority() is False


def test_autonomous_mode_requires_execution_authority() -> None:
    intent = FinanceIntent(
        intent=Intent.TRADE_DECISION,
        execution_mode=ExecutionMode.AUTONOMOUS,
    )

    assert intent.requires_execution_authority() is True