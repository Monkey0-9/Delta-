from __future__ import annotations

from research.finalization.run_parity import run


def test_w93_python_rust_parity() -> None:
    result = run()

    assert result["status"] == "PASS"
    assert result["kernel_count"] == 6
    assert result["passed_count"] == 6
    assert result["failed_count"] == 0