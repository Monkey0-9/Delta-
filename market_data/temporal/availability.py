from __future__ import annotations

from datetime import datetime

from .point_in_time import PointInTimeObservation


def filter_point_in_time(
    observations: list[PointInTimeObservation],
    *,
    as_of: datetime,
) -> list[PointInTimeObservation]:
    """
    Return only observations that were available at `as_of`.

    This function is intentionally simple and deterministic.
    More advanced temporal indexing belongs in the storage layer.
    """

    return [
        observation
        for observation in observations
        if observation.observable_at(as_of)
    ]