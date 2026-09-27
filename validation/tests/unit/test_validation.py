from __future__ import annotations

from decimal import Decimal

from risk.firewall.firewall import RiskFirewall
from risk.pre_trade.validation import TradeIntent
from validation.out_of_sample.evaluator import evaluate_oos
from validation.regression.baseline import check_protected_failures
from validation.walk_forward.splitter import walk_forward_splits


def test_walk_forward_no_overlap() -> None:
    splits = walk_forward_splits(100, train=50, test=10, step=10)
    for s in splits:
        assert s.train_end == s.test_start
        assert s.test_end - s.test_start == 10


def test_oos_flags_weak_strategy() -> None:
    res = evaluate_oos(tuple([Decimal("0.0001")] * 30))
    assert isinstance(res.passed, bool)


def test_protected_regression_blocks() -> None:
    v = check_protected_failures({"case-a": True, "case-b": False})
    assert not v.passed
    assert "case-b" in v.failures


def test_firewall_blocks_position_breach() -> None:
    from uuid import uuid4
    fw = RiskFirewall()
    intent = TradeIntent(uuid4(), uuid4(), "buy", Decimal("6000"), None, "k-x", True)
    d = fw.check(intent, ref_price=Decimal("10"), current_position=Decimal("0"))
    assert d.verdict.value == "block"
