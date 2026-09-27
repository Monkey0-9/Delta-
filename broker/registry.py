from __future__ import annotations

from dataclasses import dataclass

from broker.contracts import BrokerAdapter


@dataclass
class BrokerRegistration:
    broker_id: str
    display_name: str
    adapter: BrokerAdapter
    enabled: bool = True


class BrokerRegistry:

    def __init__(self):
        self._brokers: dict[
            str,
            BrokerRegistration,
        ] = {}

    def register(
        self,
        registration: BrokerRegistration,
    ) -> None:

        if registration.broker_id in self._brokers:
            raise ValueError(
                "Broker already registered"
            )

        self._brokers[
            registration.broker_id
        ] = registration

    def get(
        self,
        broker_id: str,
    ) -> BrokerRegistration:

        registration = self._brokers.get(
            broker_id
        )

        if registration is None:
            raise KeyError(
                broker_id
            )

        if not registration.enabled:
            raise RuntimeError(
                f"Broker disabled: {broker_id}"
            )

        return registration