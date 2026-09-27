"""Stress matrix: survival + detection tiers wired to release gate."""
from validation.release import ReleaseEvidence, certify_release
from validation.stress.matrix import canonical_matrix, run_matrix


def test_matrix_covers_all_shock_families():
    ids = {s.scenario_id for s in canonical_matrix()}
    assert len(ids) == 11
    assert {"VOL-20", "VOL-80", "RATE-10", "RATE-60", "CRASH-15", "CRASH-40",
            "CREDIT-50", "LIQ-70", "CORR-60", "EXEC-30", "DATA-50"} <= ids


def test_matrix_passes_and_tiers_correct():
    report = run_matrix()
    assert report.passed is True, report.failed_shocks
    tiers = {v.scenario_id: v.tier for v in report.verdicts}
    assert tiers["VOL-20"] == "survival" and tiers["CRASH-40"] == "detection"
    severe = [v for v in report.verdicts if v.tier == "detection"]
    assert all(v.breaches or v.portfolio_return <= 0 for v in severe)


def test_matrix_deterministic():
    assert run_matrix().verdicts == run_matrix().verdicts


def test_release_blocks_failed_stress():
    ev = ReleaseEvidence(True, True, True, True, True, True, True,
                         stress_passed=False)
    d = certify_release(ev)
    assert d.status.value == "blocked"
    assert any("stress_passed" in r for r in d.reasons)


def test_release_blocks_failed_finbench():
    ev = ReleaseEvidence(True, True, True, True, True, True, True,
                         True, finbench_passed=False)
    assert certify_release(ev).status.value == "blocked"
