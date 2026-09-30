from __future__ import annotations

from threading import Lock


class KillSwitch:
    """Governance-level global kill. Fail-closed default (active=True).

    P0 unification 2026-09-30: this is the GOVERNANCE view of the same
    triple-layer board owned by ``risk.kill_switch.kill_switch.KillSwitchBoard``.
    Prefer the board (global/strategy/broker) for new code; this shim stays
    for backward compat. Use :meth:`bind_to_board` so both views agree —
    an unwired second switch is a split-brain hazard.
    """

    def __init__(self):
        self._lock = Lock()
        self._active = True
        self._board = None

    def bind_to_board(self, board) -> None:
        """Mirror the board's GLOBAL layer into this shim (one direction)."""
        self._board = board
        try:
            active = bool(board.any_active())
        except Exception:
            active = True
        with self._lock:
            self._active = active

    def activate(self) -> None:
        with self._lock:
            self._active = True

    def deactivate(self) -> None:
        with self._lock:
            self._active = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def assert_execution_allowed(self) -> None:
        if self.active:
            raise RuntimeError(
                "GLOBAL KILL SWITCH ACTIVE"
            )