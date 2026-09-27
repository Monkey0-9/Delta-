from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalLLM:
    name: str
    endpoint: str
    timeout_seconds: float = 30.0


class LocalLLMRouter:

    def __init__(
        self,
        models: list[LocalLLM],
    ):
        if not models:
            raise ValueError(
                "no local models registered"
            )

        self.models = {
            model.name: model
            for model in models
        }

    def route(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> dict:

        selected = (
            self.models[
                model
            ]
            if model
            else next(
                iter(
                    self.models.values()
                )
            )
        )

        payload = {
            "model": selected.name,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False,
        }

        request = urllib.request.Request(
            selected.endpoint,
            data=json.dumps(
                payload
            ).encode(),
            headers={
                "Content-Type":
                    "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(
            request,
            timeout=selected.timeout_seconds,
        ) as response:

            return {
                "model": selected.name,
                "result": json.loads(
                    response.read().decode()
                ),
            }