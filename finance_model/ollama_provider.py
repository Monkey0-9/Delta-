from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen

from .inference.provider import GenerationRequest, GenerationResult, ModelProvider


class OllamaProvider(ModelProvider):
    """Ollama local inference provider using the native /api/chat endpoint."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        timeout_s: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def generate(self, request: GenerationRequest) -> GenerationResult:
        payload = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
            "options": {"temperature": request.temperature},
        }

        http_request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urlopen(http_request, timeout=self.timeout_s) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"Ollama is unavailable at {self.base_url}: {exc}"
            ) from exc

        return GenerationResult(
            text=str(result.get("message", {}).get("content", "")),
            model=str(result.get("model", request.model)),
            prompt_tokens=result.get("prompt_eval_count"),
            completion_tokens=result.get("eval_count"),
            latency_ms=(time.perf_counter() - started) * 1000.0,
        )
