"""P5: alert fan-out (terminal+audit always; TG/WA vault-gated, default off)."""
import pytest

from delta_os.alerting import AlertFanout
from delta_os.vault import Vault


def _vault(tmp_path):
    v = Vault(tmp_path / "vault.bin")
    v.unlock("pw-123")
    return v


def _alert():
    return {"timestamp": "2026-10-02T00:00:00+00:00", "level": "WARNING",
            "event": "PROBE", "message": "hello"}


def test_unconfigured_messengers_stay_unconfigured(tmp_path):
    log = []
    res = AlertFanout(vault=_vault(tmp_path), compliance=None,
                      terminal_log=log).broadcast(_alert())
    assert res.terminal is True and log
    assert res.telegram == "UNCONFIGURED" and res.whatsapp == "UNCONFIGURED"
    assert res.errors == []


def test_messenger_failure_recorded_never_raised(tmp_path, monkeypatch):
    import delta_os.alerting as amod

    v = _vault(tmp_path)
    v.set("telegram", {"bot_token": "bad", "chat_id": "1"})

    def boom(*a, **k):
        raise RuntimeError("net down")

    monkeypatch.setattr(amod, "send_telegram", boom)
    res = AlertFanout(vault=v, compliance=None, terminal_log=[]).broadcast(_alert())
    assert res.telegram == "FAILED"
    assert any("net down" in e for e in res.errors)


def test_messenger_send_paths_with_mocked_http(tmp_path, monkeypatch):
    import delta_os.alerting as amod

    v = _vault(tmp_path)
    v.set("telegram", {"bot_token": "tok", "chat_id": "7"})
    v.set("whatsapp", {"token": "tok", "phone_number_id": "pid", "to": "1"})

    class _Resp:
        status = 200

        def read(self, n=-1):
            return b'{"ok":true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(amod.urllib.request, "urlopen", lambda *a, **k: _Resp())
    res = AlertFanout(vault=v, compliance=None, terminal_log=[]).broadcast(_alert())
    assert res.telegram == "SENT" and res.whatsapp == "SENT"


def test_sentinel_alerts_fan_out_to_log():
    from delta_os.brain import DeltaBrain, DeltaSentinel
    from delta_os.safety import SafetyState

    log = []
    sent = DeltaSentinel(
        brain=DeltaBrain.__new__(DeltaBrain), safety_state=SafetyState(),
        equity_fn=lambda: None, positions_fn=lambda: {},
        alert_sink=lambda a: log.append(a),
        check_interval_s=3600.0)
    sent.tick_once()
    assert any("equity" in a["message"].lower() or a["event"] == "EQUITY_UNAVAILABLE"
               for a in log)


def test_agents_single_source():
    import agent.orchestrator as orch

    assert len(orch.AGENTS) == 8
