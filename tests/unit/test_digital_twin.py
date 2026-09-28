"""P1: digital-twin tail math + BEFORE/AFTER counterfactual."""
from __future__ import annotations

from simulation.digital_twin.engine import DigitalTwin, Scenario
from simulation.digital_twin.scenarios import scenario_for_universe, twin_scenarios


def test_twin_tail_fields_present_and_deterministic():
    twin = DigitalTwin(portfolio_value=100000)
    sc = Scenario("crash", {"AAPL": -0.20}, 2.0, 0.6)
    a = twin.simulate(positions={"AAPL": 100}, prices={"AAPL": 100}, scenario=sc)
    b = twin.simulate(positions={"AAPL": 100}, prices={"AAPL": 100}, scenario=sc)
    assert a == b
    assert a.portfolio_return == -0.02
    assert a.var95 > 0 and a.cvar95 >= a.var95
    assert a.max_drawdown <= 0
    assert 0.0 <= a.hhi <= 1.0
    assert a.net_exposure == 10000


def test_trim_reduces_hhi():
    twin = DigitalTwin(portfolio_value=100000)
    sc = Scenario("flat", {}, 1.0, 1.0)
    conc = twin.simulate(
        positions={"A": 900, "B": 100}, prices={"A": 100, "B": 100}, scenario=sc
    )
    balanced = twin.simulate(
        positions={"A": 500, "B": 500}, prices={"A": 100, "B": 100}, scenario=sc
    )
    assert balanced.hhi < conc.hhi


def test_universe_scenarios_cover_custom_symbols():
    uni = ("RELIANCE", "TCS", "GOLDETF")
    scs = twin_scenarios(uni)
    assert len(scs) == 5
    crash = scenario_for_universe(uni, "EQUITY_CRASH")
    assert set(crash.price_shocks) == set(uni)
    assert crash.price_shocks[uni[-1]] == -0.30


def test_compare_options_before_after():
    twin = DigitalTwin(portfolio_value=100000)
    scs = twin_scenarios(("A", "B"))
    comp = twin.compare_options(
        base_positions={"A": 0.0, "B": 0.0},
        options={"ADD_A": {"A": 10.0, "B": 0.0}},
        prices={"A": 100.0, "B": 100.0},
        scenarios=scs,
    )
    assert "BEFORE" in comp and "ADD_A" in comp
    assert len(comp["BEFORE"]) == len(scs)


def test_scan_includes_twin_block(monkeypatch):
    monkeypatch.setenv("DATA_MODE", "SIMULATION")  # offline-deterministic; live Yahoo unavailable in CI
    from trader.mandate_builder import build_mandate
    from trader.service import run_scan

    m = build_mandate(capital_text="1000000", horizon_text="week", universe_text="etfs")
    _res, _ranked, _summary, risk_text = run_scan(m, "today", None)
    assert "DIGITAL TWIN (BEFORE risk)" in risk_text
    assert "VaR95" in risk_text
