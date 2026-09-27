from decimal import Decimal

from governance.execution_policy import (
    ExecutionContext,
    authorize,
)
from trader.mandate import (
    AutonomyMode,
    TradingMandate,
)


def test_trader_to_risk_pipeline():

    mandate = TradingMandate(
        account_id="TRADER-1",
        universe=("AAPL", "MSFT", "NVDA"),
        allowed_modes=frozenset(
            {AutonomyMode.PAPER}
        ),
        max_position_notional=Decimal(
            "100000"
        ),
        max_order_notional=Decimal(
            "10000"
        ),
        max_daily_turnover=Decimal(
            "50000"
        ),
    )

    context = ExecutionContext(
        market_open=True,
        data_fresh=True,
        broker_healthy=True,
        risk_approved=True,
        authorization_valid=True,
        kill_switch_active=False,
        model_eligible=True,
        uncertainty_acceptable=True,
        duplicate_order=False,
    )

    decision = authorize(
        mandate,
        AutonomyMode.PAPER,
        order_notional=Decimal(
            "5000"
        ),
        context=context,
    )

    assert decision.allowed