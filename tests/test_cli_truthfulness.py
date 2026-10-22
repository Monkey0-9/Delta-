"""CLI truthfulness regression tests for runtime status and model readiness."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import apps.cli.main as cli


def test_model_doctor_does_not_claim_inference_ready(monkeypatch, capsys):
    fake_torch = SimpleNamespace(
        __version__="test",
        cuda=SimpleNamespace(is_available=lambda: False),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    cli.model_doctor()
    output = capsys.readouterr().out

    assert "Toolchain check: COMPLETE" in output
    assert "Inference status: NOT VERIFIED" in output
    assert "Model platform: READY" not in output


def test_cli_status_uses_runtime_status_handler(monkeypatch, capsys):
    from delta_os import repl

    class FakeTerminal:
        def handle(self, command):
            assert command == "/status"
            return ("DYNAMIC RUNTIME STATUS", False)

    monkeypatch.setattr(repl, "Terminal", FakeTerminal)
    cli.status()

    assert "DYNAMIC RUNTIME STATUS" in capsys.readouterr().out
