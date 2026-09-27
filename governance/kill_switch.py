from __future__ import annotations

from threading import Lock


class KillSwitch:

    def __init__(self):
        self._lock = Lock()
        self._active = True

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