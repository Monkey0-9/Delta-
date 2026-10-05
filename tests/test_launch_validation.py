"""Launch checklists: strategy 11 + LLM 12 + shared 5, incl. critical gates."""
from finance_model.llm_validation import (
    check_ci, check_cost, check_evals, check_golden, check_judge, check_latency,
    check_observability, check_prompt_robust, check_redteam, check_resilience,
    check_rollback, check_schema,
)
from finance_model.llm_validation import launch_verdict as llm_verdict
from governance.launch_gates import (
    check_docs, check_killswitch, check_monitoring, check_oncall, check_signoff,
    unified_launch,
)
from research.strategy_validation import (
    block_bootstrap, check_compliance, check_costs, check_data_quality,
    check_oos, check_overfit, check_paper, check_pit, check_regimes,
    check_risk, check_survivorship, check_walkforward,
)
from research.strategy_validation import launch_verdict as strat_verdict


def _good_strategy():
    rets = [0.001 + 0.0005 * ((i % 5) - 2) for i in range(252)]
    eq = [1.0]
    for r in rets:
        eq.append(eq[-1] * (1 + r))
    return [
        check_oos(1000, 300, 1.2),
        check_walkforward([0.8, 0.6, -0.1, 0.9, 0.7]),
        check_overfit(1.2, [1.1, 1.0, 1.15],
                      block_bootstrap([0.01] * 50 + [-0.005] * 10, n_iter=50)),
        check_pit(True, False),
        check_survivorship(900, 100),
        check_costs(30.0, 18.0, 8.0),
        check_regimes({"bull": 0.2, "bear": 0.02, "highvol": 0.01,
                       "2008": 0.0, "2020": 0.03, "2022": -0.01}),
        check_risk(rets, eq),
        check_paper(90, 500, "live-paper"),
        check_data_quality(3, 0, True, 200.0),
        check_compliance(True, True, True, True),
    ]


def _good_llm():
    return [
        check_golden(600, 80, "production"),
        check_evals(0.9, 0.88, 0.97),
        check_judge([1, 2, 3, 4, 5], [1.1, 1.9, 3.2, 3.8, 5.1]),
        check_latency([200, 300, 250, 400, 350] * 20, 2000.0, 3),
        check_cost(1500.0, 10000.0, 0.002, 5000.0),
        check_prompt_robust(95, 100, "You are a finance assistant."),
        check_redteam(98, 100, "Revenue was strong this quarter."),
        check_schema(98, 100, True),
        check_observability(1.0, True, True),
        check_resilience(True, True, True, 10),
        check_rollback(True, True, True),
        check_ci(True, True),
    ]


def _good_shared():
    return [
        check_signoff({"quant": True, "engineering": True, "risk": True,
                       "infosec": True, "operations": True}, True),
        check_docs(True, True, True),
        check_monitoring(True, True, True),
        check_killswitch(True, 7.0),
        check_oncall(True, True, True),
    ]


def test_strategy_all_11_pass():
    checks = _good_strategy()
    assert len(checks) == 11 and all(c.ok for c in checks), [c for c in checks if not c.ok]
    v = strat_verdict(checks)
    assert v["launch"] and v["failed"] == [] and not v["critical_block"]


def test_strategy_critical_gate_overfit_blocks():
    checks = _good_strategy()
    # Kill the edge under perturbation -> overfit veto
    checks[2] = check_overfit(1.2, [0.1, -0.2, 0.05],
                              block_bootstrap([0.01] * 50 + [-0.005] * 10, n_iter=50))
    assert not checks[2].ok
    v = strat_verdict(checks)
    assert not v["launch"] and v["critical_block"] and "3-overfit" in v["failed"]


def test_strategy_each_check_can_fail():
    assert not check_oos(1000, 50, 1.2).ok  # <20% OOS
    assert not check_walkforward([-1, -2, -3]).ok
    assert not check_pit(False, False).ok
    assert not check_survivorship(1000, 0).ok  # no delisted
    assert not check_costs(30.0, 18.0, -5.0).ok  # dies at 2x
    assert not check_regimes({"bull": 0.2}).ok  # missing regimes
    assert not check_paper(5, 10, "live-paper").ok  # < cycle
    assert not check_data_quality(1, 3, False, 5000.0).ok
    assert not check_compliance(False, True, True, True).ok
    bad_rets = [-0.05] * 252
    assert not check_risk(bad_rets, [1.0, 0.5, 0.2]).ok


def test_llm_all_12_pass():
    checks = _good_llm()
    assert len(checks) == 12 and all(c.ok for c in checks), [c for c in checks if not c.ok]
    v = llm_verdict(checks)
    assert v["launch"] and not v["critical_block"]


def test_llm_critical_gate_observability_blocks():
    checks = _good_llm()
    checks[8] = check_observability(0.4, False, False)  # can't explain change
    assert not checks[8].ok
    v = llm_verdict(checks)
    assert not v["launch"] and v["critical_block"]


def test_llm_each_check_can_fail():
    assert not check_golden(20, 2, "basic").ok
    assert not check_evals(0.5, 0.9, 0.9).ok
    assert not check_judge([1, 2, 3], [3, 2, 1]).ok  # anti-correlated
    assert not check_latency([], 0, 0).ok
    assert not check_prompt_robust(50, 100, "key sk-abc123").ok  # secret + low rate
    assert not check_redteam(50, 100, "contact a@b.com ssn 123-45-6789").ok
    assert not check_schema(50, 100, False).ok
    assert not check_resilience(False, False, False, 99).ok
    assert not check_rollback(True, False, False).ok
    assert not check_ci(False, False).ok


def test_shared_all_5_pass_and_unified_launch():
    shared = _good_shared()
    assert len(shared) == 5 and all(c.ok for c in shared)
    u = unified_launch(strat_verdict(_good_strategy()),
                       llm_verdict(_good_llm()), shared)
    assert u["launch"] and u["failed"] == [] and not u["critical_block"]
    assert u["hash"] and u["strategy_hash"] and u["llm_hash"]


def test_shared_each_can_block():
    assert not check_signoff({"quant": True}, True).ok
    assert not check_docs(True, False, True).ok
    assert not check_monitoring(False, True, True).ok
    assert not check_killswitch(False, 99.0).ok  # documented-not-drilled
    assert not check_killswitch(True, 60.0).ok  # stale drill
    assert not check_oncall(True, False, True).ok
    u = unified_launch(strat_verdict(_good_strategy()),
                       llm_verdict(_good_llm()),
                       [check_killswitch(False, 99.0)])
    assert not u["launch"] and "S4-killswitch" in u["failed"]


def test_pii_masking_and_bootstrap_determinism():
    from finance_model.llm_validation import mask_pii
    assert mask_pii("mail a@b.com and 123-45-6789") == "mail [MASKED] and [MASKED]"
    a = block_bootstrap([0.01] * 40, n_iter=20, seed=7)
    b = block_bootstrap([0.01] * 40, n_iter=20, seed=7)
    assert a == b and len(a) == 20
