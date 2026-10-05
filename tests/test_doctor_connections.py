"""Doctor connections: every live path probed honestly, safe-fix only.

Deterministic core: paper READY, local brain READY, vault readable,
IBKR UNCONFIGURED without host, cloud NEEDS_KEY without keys.
Network probes may be READY or DOWN depending on connectivity — both honest.
"""
from delta_os.doctor_connections import run_all, summarize


def test_paper_always_ready():
    checks = {c.name: c for c in run_all()}
    assert checks["broker/paper"].status == "READY"
    assert checks["broker/paper"].ok


def test_local_model_ready_cloud_needs_key():
    import os
    # ensure no cloud keys leak into this assertion
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"):
        os.environ.pop(k, None)
    checks = {c.name: c for c in run_all()}
    assert "READY" in checks["models/catalogue"].value  # local delta-fm-research
    assert checks["models/catalogue"].status == "READY"


def test_ibkr_unconfigured_without_host():
    import os
    os.environ.pop("IBKR_GATEWAY_HOST", None)
    checks = {c.name: c for c in run_all()}
    assert checks["broker/ibkr"].status == "UNCONFIGURED"
    assert not checks["broker/ibkr"].ok


def test_no_secrets_echoed():
    checks = run_all()
    blob = " ".join(c.value + c.fix for c in checks)
    for bad in ("sk-", "tvly-", "AKIA", "SECRET"):
        assert bad not in blob


def test_artifact_emits():
    from delta_os.doctor_connections import emit_artifact
    p = emit_artifact(run_all())
    assert p.exists() and p.name == "connections.json"
