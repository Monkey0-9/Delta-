from datetime import (
    datetime,
    timezone,
    timedelta,
)

import pytest

from core.contracts.integration import (
    Action,
    DecisionIntent,
    RiskDecision,
    RiskStatus,
    WorldSnapshotRef,
)

from core.integration.pipeline import (
    AuthorizationDenied,
    IntegrationCoordinator,
    StaleState,
)


NOW = datetime(
    2026,
    1,
    2,
    tzinfo=timezone.utc,
)


class FakeWorld:

    def __init__(self, age=0):

        self.state = WorldSnapshotRef(
            state_id="WS-1",
            version=1,
            state_hash="a" * 64,
            as_of=(
                NOW
                - timedelta(seconds=age)
            ),
            source_hash="b" * 64,
        )

    def snapshot(self, instrument_id):
        return self.state


class FakeDecision:

    def __init__(
        self,
        action=Action.BUY,
    ):
        self.action = action
        self.calls = 0

    def decide(
        self,
        *,
        instrument_id,
        world_state,
        mandate,
    ):

        self.calls += 1

        return DecisionIntent(
            decision_id="DEC-1",
            instrument_id=instrument_id,
            action=self.action,
            quantity=10,
            horizon="1W",
            model_version="m1",
            strategy_version="s1",
            world_state=world_state,
            confidence=0.9,
            expected_return=0.05,
            expected_risk=0.02,
            evidence_ids=("E1",),
            policy_version="p1",
            generated_at=NOW,
        )


class FakeRisk:

    def __init__(
        self,
        status=RiskStatus.APPROVED,
        fresh=True,
    ):
        self.status = status
        self.fresh = fresh

    def evaluate(
        self,
        intent,
        *,
        world_state,
    ):

        quantity = (
            10
            if self.status
            is RiskStatus.APPROVED
            else 0
        )

        return RiskDecision(
            risk_decision_id="R-1",
            decision_id=intent.decision_id,
            status=self.status,
            approved_quantity=quantity,
            limits_version="L1",
            reasons=(),
            checked_at=NOW,
            data_fresh=self.fresh,
            authorization_required=True,
        )


class FakeAuth:

    def __init__(self, allowed=True):

        self.allowed = allowed
        self.calls = 0

    def authorize(self, intent):

        self.calls += 1

        return self.allowed


class FakeExecution:

    def __init__(self):

        self.calls = 0

    def submit(self, intent):

        self.calls += 1

        return {
            "broker": "SIM",
            "order_id": intent.order_id,
            "status": "SUBMITTED",
        }


def make(
    action=Action.BUY,
    risk=RiskStatus.APPROVED,
    fresh=True,
    auth=True,
    age=0,
):

    world = FakeWorld(age)

    decision = FakeDecision(action)

    risk_port = FakeRisk(
        risk,
        fresh,
    )

    auth_port = FakeAuth(auth)

    execution = FakeExecution()

    coordinator = IntegrationCoordinator(
        world,
        decision,
        risk_port,
        auth_port,
        execution,
        max_state_age_seconds=300,
    )

    return (
        coordinator,
        decision,
        risk_port,
        auth_port,
        execution,
    )


def test_buy_crosses_all_boundaries():

    (
        coordinator,
        decision,
        risk,
        auth,
        execution,
    ) = make()

    result = coordinator.run(
        instrument_id="NVDA",
        mandate={"mode": "PAPER"},
        now=NOW,
    )

    assert result.decision.action is Action.BUY

    assert (
        result.risk.status
        is RiskStatus.APPROVED
    )

    assert (
        result.execution["status"]
        == "SUBMITTED"
    )

    assert auth.calls == 1
    assert execution.calls == 1

    assert len(result.envelopes) == 5


def test_hold_never_reaches_execution():

    (
        coordinator,
        _,
        _,
        auth,
        execution,
    ) = make(Action.HOLD)

    result = coordinator.run(
        instrument_id="NVDA",
        mandate={"mode": "PAPER"},
        now=NOW,
    )

    assert result.execution is None

    assert auth.calls == 0
    assert execution.calls == 0


def test_blocked_risk_never_reaches_authorization():

    (
        coordinator,
        _,
        _,
        auth,
        execution,
    ) = make(
        Action.BUY,
        RiskStatus.BLOCKED,
    )

    result = coordinator.run(
        instrument_id="NVDA",
        mandate={"mode": "PAPER"},
        now=NOW,
    )

    assert result.execution is None

    assert auth.calls == 0
    assert execution.calls == 0


def test_stale_state_fails_closed():

    (
        coordinator,
        *_,
    ) = make(age=301)

    with pytest.raises(StaleState):

        coordinator.run(
            instrument_id="NVDA",
            mandate={},
            now=NOW,
        )


def test_authorization_denial_blocks_execution():

    (
        coordinator,
        _,
        _,
        _,
        execution,
    ) = make(auth=False)

    with pytest.raises(
        AuthorizationDenied
    ):

        coordinator.run(
            instrument_id="NVDA",
            mandate={},
            now=NOW,
        )

    assert execution.calls == 0


def test_duplicate_pipeline_is_idempotent():

    coordinator, *_ = make()

    first = coordinator.run(
        instrument_id="NVDA",
        mandate={},
        now=NOW,
    )

    second = coordinator.run(
        instrument_id="NVDA",
        mandate={},
        now=NOW,
    )

    assert (
        first.execution
        == second.execution
    )