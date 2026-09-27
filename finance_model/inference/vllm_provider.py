from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen

from .provider import GenerationRequest, GenerationResult, ModelProvider


class VLLMProvider(ModelProvider):

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        timeout_s: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def generate(self, request: GenerationRequest) -> GenerationResult:
        payload: dict[str, object] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "delta_financial_output",
                    "schema": request.response_schema,
                    "strict": True,
                },
            }

        body = json.dumps(payload).encode("utf-8")

        http_request = Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        started = time.perf_counter()

        with urlopen(http_request, timeout=self.timeout_s) as response:
            result = json.loads(response.read().decode("utf-8"))

        latency_ms = (time.perf_counter() - started) * 1000.0

        choice = result["choices"][0]["message"]

        usage = result.get("usage", {})

        return GenerationResult(
            text=choice.get("content", ""),
            model=str(result.get("model", request.model)),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_ms=latency_ms,
        )