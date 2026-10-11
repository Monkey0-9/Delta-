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

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_probe_accepts_valid_key():
    with mock.patch("urllib.request.urlopen", return_value=_Resp(200)):
        r = probe_key("openai", "sk-good")
    assert r == {"slot": "openai", "valid": True, "http": 200, "reason": "ok"}


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
