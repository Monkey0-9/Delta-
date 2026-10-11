"""P3/B: former fake-success commands perform real operations or refuse."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from delta_os.repl import Terminal


def test_fetch_reaches_real_url_and_refuses_file():
    t = Terminal()
    out, _ = t.handle("/fetch file:///etc/passwd")
    assert "BLOCKED" in out and "nothing fetched" in out, out
    out, _ = t.handle("/fetch")
    assert out.startswith("usage:"), out


def test_fork_creates_real_session():
    t = Terminal()
    out, _ = t.handle("/sessions")
    assert "none" in out, out
    out, _ = t.handle("/fork research-desk")
    assert "tab-1" in out and "research-desk" in out, out
    out, _ = t.handle("/sessions")
    assert "tab-1" in out and "research-desk" in out, out


def test_init_reports_real_workspace(tmp_path, monkeypatch):
    import os

    t = Terminal()
    monkeypatch.chdir(tmp_path)
    out, _ = t.handle("/init")
    assert "NOT FOUND" in out and "NOT initialized" in out, out
    (tmp_path / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
    out, _ = t.handle("/init")
    assert "Workspace initialized" in out and "AGENTS.md active" in out, out
    assert os.getcwd() in out
