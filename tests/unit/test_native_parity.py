from __future__ import annotations

from benchmark.native_parity import assert_parity


def test_native_parity_vectors() -> None:
    assert_parity()
