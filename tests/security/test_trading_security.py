from decimal import Decimal

import pytest

from governance.execution_policy import (
    ExecutionContext,
    authorize,
)
from trader.mandate import (
    AutonomyMode,
    TradingMandate,
)


def mandate():
    return TradingMandate(
        account_id="test",
        universe=("NVDA",),
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


def test_kill_switch_blocks():

    result = authorize(
        mandate(),
        AutonomyMode.PAPER,
        order_notional=Decimal(
            "1000"
        ),
        context=ExecutionContext(
            market_open=True,
            data_fresh=True,
            broker_healthy=True,
            risk_approved=True,
            authorization_valid=True,
            kill_switch_active=True,
            model_eligible=True,
            uncertainty_acceptable=True,
            duplicate_order=False,
        ),
    )

    assert not result.allowed


def test_stale_data_blocks():

    result = authorize(
        mandate(),
        AutonomyMode.PAPER,
        order_notional=Decimal(
            "1000"
        ),
        context=ExecutionContext(
            market_open=True,
            data_fresh=False,
            broker_healthy=True,
            risk_approved=True,
            authorization_valid=True,
            kill_switch_active=False,
            model_eligible=True,
            uncertainty_acceptable=True,
            duplicate_order=False,
        ),
    )

    assert not result.allowed


def test_missing_authorization_blocks():

    result = authorize(
        mandate(),
        AutonomyMode.PAPER,
        order_notional=Decimal(
            "1000"
        ),
        context=ExecutionContext(
            market_open=True,
            data_fresh=True,
            broker_healthy=True,
            risk_approved=True,
            authorization_valid=False,
            kill_switch_active=False,
            model_eligible=True,
            uncertainty_acceptable=True,
            duplicate_order=False,
        ),
    )

    assert not result.allowed