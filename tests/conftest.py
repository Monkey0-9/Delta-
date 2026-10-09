"""Suite hermeticity: redirect the ~/.delta session file to a per-test tmp path.

A2 kill binding persists a HALT marker to the session file on kill/unlock.
Without isolation, a test that kills (and stays HALTED by design) would
change SafetyState boot behavior for later tests in the same process
(order-dependent) and mutate the developer's real ~/.delta/session.json.
Neither is acceptable, so every test gets a fresh session file.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_delta_session(monkeypatch, tmp_path):
    import os as _os

    import delta_os.safety as _safety

    p = tmp_path / "session.json"
    # Single canonical path lives in delta_os.safety (repl resolves it
    # late-bound), so isolating safety alone covers both.
    monkeypatch.setattr(_safety, "_session_path", lambda: p)
    # A6bleed: delta_tui.app._persist_session/_restore_session do NOT go
    # through delta_os.safety — they call os.path.expanduser("~") inline.
    # Redirect bare-home expansion at the os.path seam (test-only; prod
    # behavior untouched) so the TUI can never read/write the developer's
    # real ~/.delta/session.json. Non-home expansions delegate to the real
    # implementation.
    _real_expanduser = _os.path.expanduser

    def _fake_expanduser(path):
        # os.path.expanduser also accepts path-like objects (e.g. matplotlib
        # passes a WindowsPath); only redirect bare-home expansions.
        s = path if isinstance(path, str) else (
            str(path) if isinstance(path, _os.PathLike) else None)
        if s == "~" or (isinstance(s, str)
                        and (s.startswith("~/") or s.startswith("~\\"))):
            # Preserve any subpath suffix so distinct ~/a and ~/b expansions
            # never collide at the tmp root.
            suffix = s[1:].replace("/", _os.sep).replace("\\", _os.sep)
            return str(tmp_path) + suffix
        return _real_expanduser(path)

    monkeypatch.setattr(_os.path, "expanduser", _fake_expanduser)
