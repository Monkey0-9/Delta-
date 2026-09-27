from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExecutionRequest:

    order_id: str
    asset: str
    quantity: float


@dataclass(frozen=True, slots=True)
class ExecutionAck:

    order_id: str
    accepted: bool
    broker_order_id: str | None
    message: str


class ExecutionVenue(Protocol):

    def submit(
        self,
        request: ExecutionRequest,
    ) -> ExecutionAck:
        ...


class EMS:

    def __init__(
        self,
        venue: ExecutionVenue,
    ):
        self.venue = venue

    def submit(
        self,
        request: ExecutionRequest,
    ) -> ExecutionAck:

        if request.quantity <= 0:
            raise ValueError(
                "invalid execution quantity"
            )

        return self.venue.submit(
            request
        )