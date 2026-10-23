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

    assert cli.model_doctor() is True
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

def test_model_doctor_reports_missing_torch_without_crashing(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "torch", None)

    assert cli.model_doctor() is False
    output = capsys.readouterr().out

    assert "PyTorch: NOT INSTALLED" in output
    assert "Toolchain check: INCOMPLETE" in output
    assert "Inference status: NOT VERIFIED" in output

def test_default_doctor_does_not_require_training_stack(monkeypatch, capsys):
    def forbidden_model_probe():
        raise AssertionError("delta doctor must not require PyTorch")

    monkeypatch.setattr(cli, "model_doctor", forbidden_model_probe)
    cli.doctor()
    output = capsys.readouterr().out

    assert "DELTA CLI DOCTOR" in output
    assert "Runtime: READY" in output
    assert "Model inference: NOT VERIFIED" in output
    assert "Execution: PAPER/research only" in output

