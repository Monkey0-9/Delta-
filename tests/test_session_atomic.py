"""A5 session-file hardening tests (atomicity + merge + no silent wipes).

Covers:
- corrupt session.json -> raw text backed up to a timestamped sibling, fresh marker works.
- _save_session failure (unwritable path) -> no raise, visible warning.
- unreadable safety mode -> write skipped, MANUAL never invented.
- read-merge: existing keys (incl. a prior HALTED marker) survive saves.
- writes are atomic: unique tmp per call, no .tmp leftovers, valid JSON afterwards.
- backup rotation: first backup survives later corrupt events, capped at 3.
- load path is pure read: never writes a backup.
- public read_session_dict kept in sync with the _read_session_dict alias.
- release secret scan ignores truncated doc examples (USER_GUIDE /key samples).
"""
from __future__ import annotations

import json
import sys

import pytest

sys.path.insert(0, ".")


def _backups(p):
    return sorted(p.parent.glob(p.name + "*.bak*"), key=lambda q: q.name)


@pytest.fixture
def _isolated_session(monkeypatch, tmp_path):
    # Single canonical path lives in delta_os.safety; repl resolves it
    # late-bound, so isolating safety alone is sufficient (dedup proof).
    import delta_os.safety as _safety

    p = tmp_path / "session.json"
    monkeypatch.setattr(_safety, "_session_path", lambda: p)
    return p


def test_corrupt_persist_baks_up_and_fresh_marker_works(_isolated_session):
    import warnings

    from delta_os.safety import persist_safety_mode, read_persisted_safety_mode

    _isolated_session.write_text("not-json{{{", encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        persist_safety_mode("HALTED")
    baks = _backups(_isolated_session)
    assert len(baks) == 1, "corrupt content must be backed up, never wiped silently"
    assert baks[0].read_text(encoding="utf-8") == "not-json{{{"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert read_persisted_safety_mode() == "HALTED"
    assert list(_isolated_session.parent.glob("*.tmp")) == []


def test_corrupt_save_baks_up_and_merges(_isolated_session):
    import warnings

    from delta_os import repl as _repl

    term = _repl.Terminal()
    _isolated_session.write_text("garbage[[[", encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _repl._save_session(term)
    baks = _backups(_isolated_session)
    assert len(baks) == 1 and baks[0].read_text(encoding="utf-8") == "garbage[[["
    d = json.loads(_isolated_session.read_text(encoding="utf-8"))
    assert d["safety_mode"] == str(term.safety.mode)
    assert "watchlist" in d


def test_unwritable_path_no_raise_warns(_isolated_session, monkeypatch, tmp_path):
    import warnings

    import delta_os.repl as _repl
    import delta_os.safety as _safety

    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a dir", encoding="utf-8")
    monkeypatch.setattr(_safety, "_session_path", lambda: blocker / "session.json")
    term = _repl.Terminal()
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        _repl._save_session(term)  # must not raise
    assert any(issubclass(w.category, UserWarning) for w in rec), \
        "save failure must warn visibly, never pass silently"
    assert not (blocker / "session.json").exists()


def test_unreadable_mode_skips_write_never_invents_manual(_isolated_session):
    import warnings

    from delta_os import repl as _repl

    _isolated_session.write_text(json.dumps({"safety_mode": "HALTED",
                                             "watchlist": ["NVDA"]}),
                                 encoding="utf-8")

    class _BadSafety:
        @property
        def mode(self):  # noqa: D102
            raise RuntimeError("mode unreadable")

    class _StubTerm:
        watchlist = ["MSFT"]
        theme = "monokai"
        workspace = "EQUITIES-ALPHA"
        model_name = "delta-fm-research"
        effort = "AUTO"
        thinking = "SUMMARY"
        broker_name = "paper"
        safety = _BadSafety()

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        _repl._save_session(_StubTerm())  # must not raise
    assert any("never inventing" in str(w.message) for w in rec)
    # The pre-existing HALTED marker must survive untouched — no MANUAL write.
    d = json.loads(_isolated_session.read_text(encoding="utf-8"))
    assert d["safety_mode"] == "HALTED"
    assert d["watchlist"] == ["NVDA"]


def test_save_merges_preserves_existing_keys(_isolated_session):
    import warnings

    from delta_os import repl as _repl

    _isolated_session.write_text(json.dumps({"custom_key": "keep-me",
                                             "watchlist": ["OLD"],
                                             "safety_mode": "MANUAL"}),
                                 encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        term = _repl.Terminal()
    term.watchlist = ["NVDA"]
    term.safety.kill_all([], actor="test")
    assert term.safety.mode == "HALTED"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _repl._save_session(term)
    d = json.loads(_isolated_session.read_text(encoding="utf-8"))
    assert d["custom_key"] == "keep-me", "merge must preserve unknown keys"
    assert d["watchlist"] == ["NVDA"]
    assert d["safety_mode"] == "HALTED"


def test_persist_merges_preserves_existing_keys(_isolated_session):
    import warnings

    from delta_os.safety import persist_safety_mode

    _isolated_session.write_text(json.dumps({"watchlist": ["NVDA"],
                                             "theme": "solarized"}),
                                 encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        persist_safety_mode("HALTED")
    d = json.loads(_isolated_session.read_text(encoding="utf-8"))
    assert d == {"watchlist": ["NVDA"], "theme": "solarized",
                 "safety_mode": "HALTED"}


def test_load_failure_warns_but_never_raises(_isolated_session):
    import warnings

    from delta_os import repl as _repl

    _isolated_session.write_text("broken{{{", encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        term = _repl.Terminal()
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        _repl._load_session(term)  # must not raise
    assert any(issubclass(w.category, UserWarning) for w in rec)


def test_atomic_write_unique_tmp_both_survive_no_leftovers(tmp_path):
    from delta_os.safety import atomic_write_json

    p = tmp_path / "session.json"
    atomic_write_json(str(p), {"n": 1})  # str paths accepted
    atomic_write_json(p, {"n": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"n": 2}
    assert list(tmp_path.glob("*.tmp")) == [], "unique tmp must never leak"


def test_atomic_write_failure_cleans_own_tmp(tmp_path, monkeypatch):
    import os as _os

    from delta_os.safety import atomic_write_json

    p = tmp_path / "session.json"

    def _boom(*a, **k):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(_os, "replace", _boom)
    with pytest.raises(RuntimeError):
        atomic_write_json(p, {"n": 1})
    assert list(tmp_path.glob("*.tmp")) == []
    assert not p.exists()


def test_bak_rotation_keeps_first_backup_and_caps_at_three(_isolated_session):
    import warnings

    from delta_os.safety import persist_safety_mode

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _isolated_session.write_text("corrupt-A{{{", encoding="utf-8")
        persist_safety_mode("HALTED")
        first = _backups(_isolated_session)
        assert len(first) == 1 and first[0].read_text(encoding="utf-8") == "corrupt-A{{{"
        _isolated_session.write_text("corrupt-B[[[", encoding="utf-8")
        persist_safety_mode("MANUAL")
    texts = {b.read_text(encoding="utf-8") for b in _backups(_isolated_session)}
    assert texts == {"corrupt-A{{{", "corrupt-B[[["}
    assert len(texts) == 2, "rotation must keep the first backup, never truncate it"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for i in range(5):
            _isolated_session.write_text(f"corrupt-{i}###", encoding="utf-8")
            persist_safety_mode("MANUAL")
    assert len(_backups(_isolated_session)) <= 3, "backups must stay bounded"


def test_public_read_session_dict_alias_matches(_isolated_session):
    import warnings

    import delta_os.safety as _safety

    assert callable(_safety.read_session_dict)
    assert "read_session_dict" in _safety.__all__
    _isolated_session.write_text(json.dumps({"a": 1}), encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert _safety.read_session_dict(_isolated_session) == ({"a": 1}, False)
        assert _safety._read_session_dict(_isolated_session) == ({"a": 1}, False)
        assert _safety.read_session_dict(str(_isolated_session))[0] == {"a": 1}


def test_load_path_creates_no_backup(_isolated_session):
    import warnings

    from delta_os import repl as _repl

    _isolated_session.write_text("broken{{{", encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        term = _repl.Terminal()
        _repl._load_session(term)  # pure read: warn + defaults, no .bak
    assert _backups(_isolated_session) == []


def test_scan_skips_doc_examples_but_still_catches_real_shape():
    import sys
    from pathlib import Path

    sys.path.insert(0, "scripts")
    from release_certify import secret_scan

    sc = secret_scan()
    assert all("USER_GUIDE" not in h for h in sc.get("hits", [])), \
        f"guide doc examples must not flag: {sc.get('hits')}"
    probe = Path("zz_tmp_secret_probe_CHECK.py")
    try:
        probe.write_text('KEY = "tvly-abc123-real-shape"\n', encoding="utf-8")
        sc2 = secret_scan()
        assert any("zz_tmp_secret_probe_CHECK" in h for h in sc2["hits"]), \
            "scanner must still catch real key-shaped lines"
    finally:
        probe.unlink(missing_ok=True)
