from __future__ import annotations

import threading


class IdempotencyStore:

    def __init__(self):
        self._lock = threading.Lock()
        self._keys: set[str] = set()

    def reserve(
        self,
        key: str,
    ) -> bool:

        if not key:
            raise ValueError(
                "empty idempotency key"
            )

        with self._lock:

            if key in self._keys:
                return False

            self._keys.add(key)
            return True