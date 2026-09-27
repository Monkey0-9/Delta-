from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True, slots=True)
class Experience:

    experience_id: str
    failure_id: str
    state_hash: str
    lesson: str
    action_taken: str
    outcome: float
    regime: str
    model_version: str

    @property
    def fingerprint(self) -> str:

        payload = {
            "experience_id": self.experience_id,
            "failure_id": self.failure_id,
            "state_hash": self.state_hash,
            "lesson": self.lesson,
            "action_taken": self.action_taken,
            "outcome": self.outcome,
            "regime": self.regime,
            "model_version": self.model_version,
        }

        return hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()


class ExperienceStore:

    def __init__(self):

        self._records: dict[
            str,
            Experience,
        ] = {}

    def put(
        self,
        experience: Experience,
    ) -> None:

        existing = self._records.get(
            experience.experience_id
        )

        if (
            existing is not None
            and existing.fingerprint
            != experience.fingerprint
        ):
            raise ValueError(
                "experience identity collision"
            )

        self._records[
            experience.experience_id
        ] = experience

    def get(
        self,
        experience_id: str,
    ) -> Experience:

        return self._records[
            experience_id
        ]

    def search_regime(
        self,
        regime: str,
    ) -> tuple[Experience, ...]:

        return tuple(
            record
            for record in self._records.values()
            if record.regime == regime
        )