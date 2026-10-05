"""Canonical command bus: typed Request/Response/Event/Error, no invented state."""
import pytest
from core.command_bus import (CommandError, CommandRequest, dispatch,
                              submit_event)


def test_dispatch_known():
    r = dispatch(CommandRequest(command="/risk", mode="PAPER"))
    assert "risk" in r.screen and "[PAPER]" in r.output


def test_dispatch_needs_symbol_no_default():
    r = dispatch(CommandRequest(command="book", arg=""))
    assert "needs a symbol" in r.output


def test_unknown_raises_with_hint():
    with pytest.raises(CommandError):
        dispatch(CommandRequest(command="/nope-not-real"))


def test_event_kinds_guarded():
    e = submit_event("trade", "PENDING", "awaiting broker ack")
    assert e.kind == "PENDING"
    with pytest.raises(CommandError):
        submit_event("trade", "FILLED-FAKE")
