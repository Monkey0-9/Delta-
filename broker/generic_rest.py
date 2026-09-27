from __future__ import annotations

import json
import urllib.request
from decimal import Decimal
from typing import Any

from broker.contracts import (
    BrokerAccount,
    BrokerAdapter,
    BrokerOrder,
    BrokerOrderResult,
    BrokerPosition,
)


class GenericRESTBroker(BrokerAdapter):

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        endpoints: dict[str, str],
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.endpoints = endpoints
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:

        url = (
            self.base_url
            + "/"
            + path.lstrip("/")
        )

        body = None

        if payload is not None:
            body = json.dumps(
                payload
            ).encode()

        request = urllib.request.Request(
            url=url,
            data=body,
            method=method,
            headers={
                "Authorization":
                    f"Bearer {self.api_key}",
                "Content-Type":
                    "application/json",
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=self.timeout,
        ) as response:

            return json.loads(
                response.read().decode()
            )

    def health(self) -> bool:

        try:
            self._request(
                "GET",
                self.endpoints["health"],
            )
            return True
        except Exception:
            return False

    def account(self) -> BrokerAccount:

        data = self._request(
            "GET",
            self.endpoints["account"],
        )

        return BrokerAccount(
            account_id=str(
                data["account_id"]
            ),
            equity=Decimal(
                str(data["equity"])
            ),
            cash=Decimal(
                str(data["cash"])
            ),
            buying_power=Decimal(
                str(data["buying_power"])
            ),
        )

    def positions(
        self,
    ) -> list[BrokerPosition]:

        data = self._request(
            "GET",
            self.endpoints["positions"],
        )

        return [
            BrokerPosition(
                symbol=str(row["symbol"]),
                quantity=Decimal(
                    str(row["quantity"])
                ),
                average_price=Decimal(
                    str(row["average_price"])
                ),
            )
            for row in data
        ]

    def submit(
        self,
        order: BrokerOrder,
    ) -> BrokerOrderResult:

        payload = {
            "client_order_id":
                order.client_order_id,
            "symbol":
                order.symbol,
            "side":
                order.side.value,
            "type":
                order.order_type.value,
            "quantity":
                str(order.quantity),
            "time_in_force":
                order.time_in_force.value,
        }

        if order.limit_price is not None:
            payload["limit_price"] = str(
                order.limit_price
            )

        if order.stop_price is not None:
            payload["stop_price"] = str(
                order.stop_price
            )

        data = self._request(
            "POST",
            self.endpoints["submit"],
            payload,
        )

        return BrokerOrderResult(
            broker_order_id=str(
                data["broker_order_id"]
            ),
            client_order_id=
                order.client_order_id,
            status=str(
                data["status"]
            ),
            raw=data,
        )

    def cancel(
        self,
        broker_order_id: str,
    ) -> None:

        self._request(
            "POST",
            self.endpoints["cancel"].format(
                broker_order_id
            ),
        )

    def order_status(
        self,
        broker_order_id: str,
    ) -> BrokerOrderResult:

        data = self._request(
            "GET",
            self.endpoints["status"].format(
                broker_order_id
            ),
        )

        return BrokerOrderResult(
            broker_order_id=
                str(data["broker_order_id"]),
            client_order_id=
                str(data["client_order_id"]),
            status=
                str(data["status"]),
            raw=data,
        )

    def reconcile(
        self,
    ) -> list[BrokerOrderResult]:

        data = self._request(
            "GET",
            self.endpoints["open_orders"],
        )

        return [
            BrokerOrderResult(
                broker_order_id=
                    str(row["broker_order_id"]),
                client_order_id=
                    str(row["client_order_id"]),
                status=
                    str(row["status"]),
                raw=row,
            )
            for row in data
        ]