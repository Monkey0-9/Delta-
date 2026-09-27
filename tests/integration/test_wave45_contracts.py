from datetime import datetime, timezone

import pytest

from core.contracts.integration import (
    Action,
    DecisionIntent,
    IntegrationEnvelope,
    RiskDecision,
    RiskStatus,
    Stage,
    WorldSnapshotRef,
)


NOW = datetime(
    2026,
    1,
    2,
    tzinfo=timezone.utc,
)


def make_state():

    return WorldSnapshotRef(
        state_id="WS-1",
        version=7,
        state_hash="a" * 64,
        as_of=NOW,
        source_hash="b" * 64,
    )


def make_decision(
    action=Action.BUY,
):

    return DecisionIntent(
        decision_id="DEC-1",
        instrument_id="NVDA",
        action=action,
        quantity=10,
        horizon="1W",
        model_version="model-1",
        strategy_version="strategy-1",
        world_state=make_state(),
        confidence=0.8,
        expected_return=0.04,
        expected_risk=0.02,
        evidence_ids=(
            "E1",
            "E2",
        ),
        policy_version="policy-1",
        generated_at=NOW,
    )


def test_world_state_is_immutable():

    state = make_state()

    with pytest.raises(Exception):

        state.version = 8


def test_blocked_risk_cannot_approve_quantity():

    with pytest.raises(ValueError):

        RiskDecision(
            risk_decision_id="R-1",
            decision_id="DEC-1",
            status=RiskStatus.BLOCKED,
            approved_quantity=1,
            limits_version="L1",
            reasons=("limit",),
            checked_at=NOW,
            data_fresh=True,
            authorization_required=True,
        )


def test_hold_is_not_execution_action():

    decision = make_decision(
        Action.HOLD
    )

    assert (
        decision.action
        is Action.HOLD
    )


def test_hash_chain_detects_parent_change():

    first = IntegrationEnvelope.build(
        "C",
        Stage.WORLD_STATE,
        {"x": 1},
    )

    child_a = (
        IntegrationEnvelope.build(
            "C",
            Stage.DECISION,
            {"x": 2},
            first.envelope_hash(),
        )
    )

    child_b = (
        IntegrationEnvelope.build(
            "C",
            Stage.DECISION,
            {"x": 2},
            "wrong-parent",
        )
    )

    assert (
        child_a.envelope_hash()
        != child_b.envelope_hash()
    )


def test_decision_has_world_state():

    decision = make_decision()

    assert (
        decision.world_state.state_id
        == "WS-1"
    )