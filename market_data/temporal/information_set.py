from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar

from .point_in_time import PointInTimeObservation

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class InformationSet(Generic[T]):
    """
    Immutable snapshot of information observable at a
    particular research timestamp.
    """

    as_of: datetime
    observations: tuple[
        PointInTimeObservation[T],
        ...,
    ]

    @classmethod
    def build(
        cls,
        observations: list[PointInTimeObservation[T]],
        *,
        as_of: datetime,
    ) -> "InformationSet[T]":
        visible = tuple(
            observation
            for observation in observations
            if observation.observable_at(as_of)
        )

        return cls(
            as_of=as_of,
            observations=visible,
        )

    def __len__(self) -> int:
        return len(self.observations)