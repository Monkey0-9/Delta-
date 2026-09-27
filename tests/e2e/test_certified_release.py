"""E2E: computed certification certifies; any tampered gate blocks release."""
from validation.certification import run_certification
from validation.final_certification import build_certification
from validation.release import certify_release


def test_e2e_computed_certified_release():
    out = run_certification()
    assert out["decision"].status.value == "certified"

    import hashlib

    digest = hashlib.sha256(str(sorted(out["gates"].items())).encode()).hexdigest()
    final = build_certification(
        python_tests=285,
        rust_tests=10,
        certification_hash=digest,
        certified=out["decision"].status.value == "certified",
    )
    assert final.certified is True
    assert len(final.certification_hash) == 64


def test_e2e_each_gate_blocks_when_failed():
    from dataclasses import replace

    out = run_certification()
    for field in ("stress_passed", "finbench_passed", "walkforward_passed",
                  "replay_deterministic", "chaos_passed", "security_passed",
                  "perf_within_budget", "protected_failures_passed"):
        tampered = replace(out["evidence"], **{field: False})
        assert certify_release(tampered).status.value == "blocked", field
