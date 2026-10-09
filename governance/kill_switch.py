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
        """Mirror the board's GLOBAL layer into this shim (one direction).

        Snapshot only: callers must use activate()/deactivate() (which
        propagate to the bound board) and is_active() (live board view)
        so both views agree — an unwired second switch is split-brain.
        """
        self._board = board
        try:
            active = bool(board.any_active())
        except Exception:
            active = True
        with self._lock:
            self._active = active

    def activate(self, actor: str = "safety") -> None:
        """Activate locally AND propagate to the bound board GLOBAL layer.

        Board failures are loud (raise): a locally-active shim with an
        inactive board is split-brain fail-open for board-checked paths.
        """
        with self._lock:
            self._active = True
        board = self._board
        if board is not None:
            glob = getattr(board, "glob", None)
            if glob is not None:
                glob.activate(actor=actor)
            else:
                board.activate(actor=actor)

    def deactivate(self, actor: str = "safety") -> None:
        """Release locally AND clear the bound board GLOBAL layer.

        The board re-arms with its owning actor on PermissionError (the
        shim is the privileged safety owner). Only the GLOBAL layer is
        touched — strategy/broker halts stay fail-closed. Board failures
        are loud (raise) so unlock never claims success while halted.
        """
        with self._lock:
            self._active = False
        board = self._board
        if board is not None:
            glob = getattr(board, "glob", None)
            if glob is not None:
                if glob.active:
                    try:
                        glob.rearm(actor=actor)
                    except PermissionError:
                        glob.rearm(actor=glob.activated_by)
            elif hasattr(board, "rearm"):
                board.rearm(actor=actor)

    def is_active(self) -> bool:
        """Live kill view: board any_active() when bound, else snapshot."""
        board = self._board
        if board is not None:
            try:
                return bool(board.any_active())
            except Exception:
                pass
        with self._lock:
            return self._active

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def assert_execution_allowed(self) -> None:
        if self.active:
            raise RuntimeError(
                "GLOBAL KILL SWITCH ACTIVE"
            )