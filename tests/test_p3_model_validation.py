"""P3/L: presence is CONFIGURED; only a live probe is VALIDATED."""
from __future__ import annotations

import io
import sys
from unittest import mock

sys.path.insert(0, ".")

from delta_os.model_catalogue import probe_key, validation_status


class _Resp:
    def __init__(self, status: int = 200):
        self.status = status

    def read(self, n: int = -1) -> bytes:
        return b"{}"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_probe_accepts_valid_key():
    with mock.patch("urllib.request.urlopen", return_value=_Resp(200)):
        r = probe_key("openai", "sk-good")
    assert r["valid"] is True and r["http"] == 200 and r["reason"] == "ok"
    assert r["models"] == []  # empty body: measured-nothing, honestly


def test_probe_marks_bad_key_invalid():
    import urllib.error

    err = urllib.error.HTTPError("https://api.openai.com/v1/models", 401,
                                 "Unauthorized", {}, io.BytesIO(b"{}"))
    with mock.patch("urllib.request.urlopen", side_effect=err):
        r = probe_key("openai", "sk-bad")
    assert r["valid"] is False and r["reason"] == "invalid_key"
    assert r["http"] == 401


def test_probe_distinguishes_unreachable(monkeypatch):
    import urllib.error

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with mock.patch("urllib.request.urlopen",
                     side_effect=urllib.error.URLError("no route")):
        r = probe_key("groq", "gsk-x")
    assert r["valid"] is False and r["reason"] == "unreachable"


def test_probe_unknown_slot_and_validation_skips_keyless(monkeypatch):
    r = probe_key("nosuchslot", "k")
    assert r["valid"] is False and "no probe" in r["reason"]
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert validation_status(vault=None) == {}


def test_capability_discovery_measured_not_declared():
    import json as _json

    from delta_os.model_catalogue import describe_capabilities, probe_key

    body = _json.dumps({"data": [{"id": "deepseek-v4-pro"},
                                 {"id": "deepseek-flash"}]}).encode()

    class _Resp:
        status = 200

        def read(self, n=-1):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with mock.patch("urllib.request.urlopen", return_value=_Resp()):
        r = probe_key("deepseek", "sk-x")
    assert r["valid"] is True
    assert r["models"] == ["deepseek-flash", "deepseek-v4-pro"], r
    cap = describe_capabilities("deepseek", r)
    assert cap["measured"] is True
    assert cap["measured_models"] == ["deepseek-flash", "deepseek-v4-pro"]
    # No probe, no measurement — declared table never poses as measured.
    cap0 = describe_capabilities("openai", None)
    assert cap0["measured"] is False and cap0["measured_models"] == []
    assert cap0["probed"] is False
