from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True, slots=True)
class Reservation:
    key: str
    owner: str


class IdempotencyStore:
    """
    Thread-safe in-process idempotency store.

    Lifecycle:

        reserve()
            ↓
        execution
            ↓
        complete()

    put_if_absent() is retained as a compatibility API for
    existing Wave45 callers/tests.

    Production execution should reserve BEFORE submitting an order.
    """

    def __init__(self) -> None:
        self._lock = Lock()

        self._reservations: dict[str, Reservation] = {}
        self._results: dict[str, object] = {}

    def reserve(
        self,
        key: str,
        owner: str,
    ) -> bool:
        """
        Atomically reserve an idempotency key.

        Returns True when:
            - the key did not exist and is now reserved
            - the same owner already owns the reservation

        Returns False when another owner already owns the key.
        """

        if not key:
            raise ValueError("idempotency key required")

        if not owner:
            raise ValueError("idempotency owner required")

        with self._lock:
            existing = self._reservations.get(key)

            if existing is not None:
                return existing.owner == owner

            self._reservations[key] = Reservation(
                key=key,
                owner=owner,
            )

            return True

    def put_if_absent(
        self,
        key: str,
        value: object,
    ) -> tuple[bool, object | None]:
        """
        Atomically store a completed result if one does not already exist.

        Returns:

            (True, None)
                if this call inserted the result.

            (False, previous)
                if a result already existed.

        This method exists for Wave45 compatibility.
        """

        if not key:
            raise ValueError("idempotency key required")

        with self._lock:
            existing = self._results.get(key)

            if existing is not None:
                return False, existing

            self._results[key] = value

            return True, None

    def complete(
        self,
        key: str,
        result: object,
    ) -> None:
        """
        Mark a previously reserved key as completed.
        """

        if not key:
            raise ValueError("idempotency key required")

        with self._lock:
            if key not in self._reservations:
                raise RuntimeError(
                    "cannot complete unreserved key"
                )

            self._results[key] = result

    def result(
        self,
        key: str,
    ) -> object | None:
        """
        Return the previously completed result, if present.
        """

        if not key:
            raise ValueError("idempotency key required")

        with self._lock:
            return self._results.get(key)

    def is_completed(
        self,
        key: str,
    ) -> bool:
        """
        Return True when a completed result exists.
        """

        with self._lock:
            return key in self._results

    def is_reserved(
        self,
        key: str,
    ) -> bool:
        """
        Return True when the key has been reserved.
        """

        with self._lock:
            return key in self._reservations

    def clear(
        self,
        key: str,
    ) -> None:
        """
        Test/reset helper.

        This should not be used by the live execution path.
        """

        if not key:
            raise ValueError("idempotency key required")

        with self._lock:
            self._reservations.pop(key, None)
            self._results.pop(key, None)