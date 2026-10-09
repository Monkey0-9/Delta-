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
    import delta_os.safety as _safety

    p = tmp_path / "session.json"
    # Single canonical path lives in delta_os.safety (repl resolves it
    # late-bound), so isolating safety alone covers both.
    monkeypatch.setattr(_safety, "_session_path", lambda: p)
