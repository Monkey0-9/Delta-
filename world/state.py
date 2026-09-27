from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Mapping


def _utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        raise ValueError(
            "timestamp must be timezone-aware"
        )

    return timestamp.astimezone(timezone.utc)


def _hash(payload: object) -> str:

    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()

    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class WorldState:

    state_id: str
    version: int

    timestamp: datetime

    prices: Mapping[str, float]

    positions: Mapping[str, float]

    features: Mapping[str, float]

    regime: str

    source_hash: str

    state_hash: str

    @staticmethod
    def create(
        *,
        state_id: str,
        version: int,
        timestamp: datetime,
        prices: Mapping[str, float],
        positions: Mapping[str, float],
        features: Mapping[str, float],
        regime: str,
        source_hash: str,
    ) -> "WorldState":

        timestamp = _utc(timestamp)

        payload = {
            "state_id": state_id,
            "version": version,
            "timestamp": timestamp.isoformat(),
            "prices": dict(
                sorted(prices.items())
            ),
            "positions": dict(
                sorted(positions.items())
            ),
            "features": dict(
                sorted(features.items())
            ),
            "regime": regime,
            "source_hash": source_hash,
        }

        return WorldState(
            state_id=state_id,
            version=version,
            timestamp=timestamp,
            prices=dict(prices),
            positions=dict(positions),
            features=dict(features),
            regime=regime,
            source_hash=source_hash,
            state_hash=_hash(payload),
        )


class WorldStateStore:

    def __init__(self) -> None:
        self._states: dict[
            int,
            WorldState,
        ] = {}

    def put(
        self,
        state: WorldState,
    ) -> None:

        previous = self._states.get(
            state.version
        )

        if (
            previous is not None
            and previous.state_hash
            != state.state_hash
        ):
            raise ValueError(
                "world-state version collision"
            )

        self._states[
            state.version
        ] = state

    def get(
        self,
        version: int,
    ) -> WorldState:

        return self._states[version]

    def latest(self) -> WorldState:

        if not self._states:
            raise KeyError(
                "no world state"
            )

        return self._states[
            max(self._states)
        ]

    def replay_hash(self) -> str:

        payload = [
            {
                "version": state.version,
                "state_hash": state.state_hash,
            }
            for state in (
                self._states[k]
                for k in sorted(
                    self._states
                )
            )
        ]

        return _hash(payload)