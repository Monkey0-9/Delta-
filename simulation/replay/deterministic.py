from __future__ import annotations

import hashlib
import json


class DeterministicReplay:

    @staticmethod
    def digest(
        events,
    ) -> str:

        payload = json.dumps(
            events,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()

        return hashlib.sha256(
            payload
        ).hexdigest()

    @classmethod
    def verify(
        cls,
        events,
        expected_digest: str,
    ) -> bool:

        return (
            cls.digest(events)
            == expected_digest
        )