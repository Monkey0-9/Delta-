"""Final gates: FIN-Bench 12-dim + auto-certification computes evidence."""
from finance_model.finbench import (
    FINBench,
    citation_coverage,
    finbench_dataset,
    finbench_gate,
)
from validation.certification import run_certification


def test_finbench_covers_12_dimensions():
    dataset = finbench_dataset()
    assert len(dataset) == 12
    assert len({c.domain for c in dataset}) == 12


def test_finbench_gate_passes_oracle_fails_weak():
    dataset = finbench_dataset()
    oracle = {c.prompt: c.expected for c in dataset}
    good = FINBench(dataset).run(lambda prompt: oracle.get(prompt, ""))
    gate = finbench_gate(good)
    assert gate["passed"] is True and gate["pass_rate"] == 1.0
    assert gate["weak_domains"] == []

    bad = FINBench(dataset).run(lambda prompt: "unrelated answer")
    gate_bad = finbench_gate(bad)
    assert gate_bad["passed"] is False
    assert len(gate_bad["weak_domains"]) == 12


def test_grounding_citation_gate():
    responses = {"c1": "thesis holds [ev-1]", "c2": "no citation here"}
    cov = citation_coverage(responses, {"c1": ("ev-1",), "c2": ("ev-2",)})
    assert cov == 0.5


def test_auto_certification_computes_certified():
    out = run_certification()
    assert out["decision"].status.value == "certified", out["gates"]
    assert all(out["gates"].values())
    ev = out["evidence"]
    assert ev.stress_passed and ev.finbench_passed and ev.walkforward_passed


def test_auto_certification_tamper_blocks():
    from dataclasses import replace

    out = run_certification()
    from validation.release import certify_release

    tampered = replace(out["evidence"], stress_passed=False)
    assert certify_release(tampered).status.value == "blocked"
