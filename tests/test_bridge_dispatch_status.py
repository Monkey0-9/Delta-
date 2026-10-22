"""Bridge status regression tests: user-visible failures must not look successful."""

from types import SimpleNamespace

import pytest

from delta_os.bridge import DeltaBridge


@pytest.mark.parametrize(
    ("command", "output", "expected"),
    [
        ("/trade AAPL buy 1", "BLOCKED: stale market data", "blocked"),
        ("/ask hi", "ERROR: provider offline", "error"),
        ("/not-a-command", "unknown /not-a-command", "unknown_command"),
        ("/quote", "UNAVAILABLE: feed down", "unavailable"),
        ("/kill", "KILLED: cancel-all 0 + FROZEN.", "halted"),
        ("/trade", "usage: /trade [symbol]", "invalid_input"),
        ("/trade", "cancelled (no order sent).", "cancelled"),
        ("/status", "portfolio: UNAVAILABLE | model: UNAVAILABLE", "ok"),
        ("/risk", "risk checks completed", "ok"),
    ],
)
def test_dispatch_status_classification(command, output, expected):
    assert DeltaBridge._dispatch_status(command, output) == expected


def test_bridge_dispatch_propagates_real_status_without_constructing_runtime():
    bridge = object.__new__(DeltaBridge)
    bridge.term = SimpleNamespace(
        handle=lambda _text: ("BLOCKED: authorization required", False)
    )

    result = bridge.dispatch("/trade AAPL buy 1")

    assert result == {
        "output": "BLOCKED: authorization required",
        "status": "blocked",
    }
