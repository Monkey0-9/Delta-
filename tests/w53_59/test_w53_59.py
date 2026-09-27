from datetime import datetime, timezone

import pytest

from quant.uncertainty.engine import (
    UncertaintyVector,
    Forecast,
    UncertaintyEngine,
    DecisionAction,
)

from quant.uncertainty.calibration import (
    ProbabilityCalibrator,
)

from quant.horizon.arbitration import (
    Horizon,
    HorizonForecast,
    HorizonArbitrator,
)

from portfolio.decision import (
    Action,
    CandidateOrder,
    PortfolioDecisionEngine,
    PortfolioLimits,
    PortfolioState,
)

from risk.firewall import (
    RiskFirewall,
    RiskStatus,
)

from simulation.digital_twin.engine import (
    DigitalTwin,
    Scenario,
)

from execution.oms.state_machine import (
    OMS,
    OrderState,
)

from execution.paper.broker import (
    PaperBroker,
)

from execution.ems.adapter import (
    ExecutionRequest,
)


def uncertainty():

    return UncertaintyVector(
        aleatoric=0.10,
        epistemic=0.10,
        model_disagreement=0.10,
        data=0.05,
        regime=0.10,
        execution=0.05,
    )


def test_uncertainty_trade():

    forecast = Forecast(
        "AAPL",
        0.05,
        0.65,
        0.95,
        uncertainty(),
    )

    result = UncertaintyEngine(
        trade_confidence=0.50
    ).evaluate(
        forecast
    )

    assert result.action == DecisionAction.TRADE


def test_high_uncertainty_abstains():

    high = UncertaintyVector(
        0.9,
        0.9,
        0.9,
        0.9,
        0.9,
        0.9,
    )

    forecast = Forecast(
        "AAPL",
        0.05,
        0.65,
        0.95,
        high,
    )

    result = UncertaintyEngine().evaluate(
        forecast
    )

    assert result.action in (
        DecisionAction.WAIT,
        DecisionAction.INVESTIGATE,
    )


def test_calibration():

    report = ProbabilityCalibrator(
        bins=5
    ).evaluate(
        [
            0.1,
            0.2,
            0.8,
            0.9,
        ],
        [
            0,
            0,
            1,
            1,
        ],
    )

    assert report.observations == 4

    assert (
        0.0
        <= report.expected_calibration_error
        <= 1.0
    )


def test_horizon_arbitration():

    result = HorizonArbitrator().arbitrate(
        [
            HorizonForecast(
                Horizon.DAILY,
                0.02,
                0.8,
                0.1,
            ),
            HorizonForecast(
                Horizon.WEEKLY,
                0.04,
                0.9,
                0.1,
            ),
        ]
    )

    assert result.expected_return > 0

    assert result.confidence > 0


def test_portfolio_limit():

    engine = PortfolioDecisionEngine(
        PortfolioLimits(
            max_position=10,
            max_gross=100,
            max_net=50,
            max_turnover=5,
        )
    )

    state = PortfolioState(
        {"AAPL": 0}
    )

    order = CandidateOrder(
        "AAPL",
        Action.BUY,
        3,
        0.02,
        0.8,
    )

    assert engine.approve(
        state,
        order,
    )


def test_risk_firewall_blocks_gross():

    firewall = RiskFirewall(
        max_quantity=10,
        max_gross=100,
    )

    result = firewall.evaluate(
        decision_id="d1",
        requested_quantity=10,
        current_gross=100,
        limits_version="v1",
    )

    assert (
        result.status
        == RiskStatus.BLOCKED
    )


def test_digital_twin():

    twin = DigitalTwin(
        portfolio_value=100000
    )

    result = twin.simulate(
        positions={
            "AAPL": 100
        },
        prices={
            "AAPL": 100
        },
        scenario=Scenario(
            "crash",
            {"AAPL": -0.20},
        ),
    )

    assert (
        result.portfolio_return
        == pytest.approx(-0.02)
    )


def test_oms_lifecycle():

    oms = OMS()

    oms.create(
        order_id="o1",
        idempotency_key="k1",
        asset="AAPL",
        quantity=1,
    )

    oms.transition(
        "o1",
        OrderState.VALIDATED,
    )

    oms.transition(
        "o1",
        OrderState.RISK_APPROVED,
    )

    oms.transition(
        "o1",
        OrderState.AUTHORIZED,
    )

    oms.transition(
        "o1",
        OrderState.SUBMITTED,
    )

    oms.transition(
        "o1",
        OrderState.ACKNOWLEDGED,
    )

    oms.transition(
        "o1",
        OrderState.FILLED,
    )

    assert (
        oms.orders["o1"].state
        == OrderState.FILLED
    )


def test_oms_rejects_illegal_transition():

    oms = OMS()

    oms.create(
        order_id="o1",
        idempotency_key="k1",
        asset="AAPL",
        quantity=1,
    )

    with pytest.raises(
        ValueError
    ):

        oms.transition(
            "o1",
            OrderState.FILLED,
        )


def test_paper_broker():

    broker = PaperBroker(
        {"AAPL": 100.0}
    )

    result = broker.submit(
        ExecutionRequest(
            "o1",
            "AAPL",
            2,
        )
    )

    assert result.accepted

    assert len(
        broker.fills
    ) == 1


def test_paper_broker_idempotent():

    broker = PaperBroker(
        {"AAPL": 100.0}
    )

    request = ExecutionRequest(
        "o1",
        "AAPL",
        2,
    )

    first = broker.submit(
        request
    )

    second = broker.submit(
        request
    )

    assert first.accepted
    assert second.accepted

    assert len(
        broker.fills
    ) == 1