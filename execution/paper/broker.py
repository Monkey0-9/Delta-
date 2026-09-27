from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time

from execution.ems.adapter import (
    ExecutionAck,
    ExecutionRequest,
)


@dataclass(frozen=True, slots=True)
class PaperFill:

    fill_id: str
    order_id: str
    asset: str
    quantity: float
    price: float
    timestamp_ns: int


class PaperBroker:

    def __init__(
        self,
        prices: dict[str, float],
    ):
        self.prices = dict(prices)
        self.orders: dict[
            str,
            ExecutionRequest,
        ] = {}

        self.fills: dict[
            str,
            PaperFill,
        ] = {}

    def submit(
        self,
        request: ExecutionRequest,
    ) -> ExecutionAck:

        if request.order_id in self.orders:

            return ExecutionAck(
                request.order_id,
                True,
                "PAPER-"
                + request.order_id,
                "idempotent replay",
            )

        price = self.prices.get(
            request.asset
        )

        if price is None:
            return ExecutionAck(
                request.order_id,
                False,
                None,
                "unknown asset",
            )

        self.orders[
            request.order_id
        ] = request

        timestamp_ns = time.time_ns()

        fill_id = hashlib.sha256(
            (
                request.order_id
                + str(timestamp_ns)
            ).encode()
        ).hexdigest()

        self.fills[
            fill_id
        ] = PaperFill(
            fill_id,
            request.order_id,
            request.asset,
            request.quantity,
            price,
            timestamp_ns,
        )

        return ExecutionAck(
            request.order_id,
            True,
            "PAPER-"
            + request.order_id,
            "filled",
        )