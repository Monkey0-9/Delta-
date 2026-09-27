from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:

    prompt_id: str
    version: str
    text: str
    digest: str


class PromptRegistry:

    def __init__(self):
        self._items: dict[
            tuple[str, str],
            Prompt,
        ] = {}

    def register(
        self,
        prompt_id: str,
        version: str,
        text: str,
    ) -> Prompt:

        digest = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

        prompt = Prompt(
            prompt_id=prompt_id,
            version=version,
            text=text,
            digest=digest,
        )

        self._items[
            (prompt_id, version)
        ] = prompt

        return prompt

    def get(
        self,
        prompt_id: str,
        version: str,
    ) -> Prompt:

        try:
            return self._items[
                (prompt_id, version)
            ]
        except KeyError:
            raise KeyError(
                f"Prompt not found: "
                f"{prompt_id}@{version}"
            )

    def render(
        self,
        prompt_id: str,
        version: str,
        **values,
    ) -> str:

        prompt = self.get(
            prompt_id,
            version,
        )

        return prompt.text.format(
            **values
        )