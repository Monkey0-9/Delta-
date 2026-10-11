"""P0-6: security gates must block — no `|| exit 0` escape hatches."""
from __future__ import annotations

from pathlib import Path


def test_no_exit_zero_hatches_in_security_workflow():
    text = (Path(__file__).resolve().parents[1]
            / ".github" / "workflows" / "security.yml").read_text()
    # Strip comments: prose may name the forbidden pattern, commands may not.
    commands = "\n".join(
        line.split("#", 1)[0] for line in text.splitlines())
    assert "|| exit 0" not in commands, (
        "security scanners must fail the workflow, not swallow failures")


def test_scheme_helper_refuses_non_http():
    import sys

    sys.path.insert(0, ".")
    import urllib.request

    import pytest

    from core.net import checked_url, urlopen_checked

    assert checked_url("https://example.com/x") == "https://example.com/x"
    with pytest.raises(ValueError):
        checked_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        checked_url(urllib.request.Request("ftp://example.com/x"))
    with pytest.raises(ValueError):
        urlopen_checked("file:///etc/passwd", timeout=1)
