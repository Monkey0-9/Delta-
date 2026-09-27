from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    version: str
    template: str
    max_context_tokens: int = 8192

    def render(self, variables: dict[str, str]) -> str:
        out = self.template
        for key, value in variables.items():
            out = out.replace("{{" + key + "}}", value)
        if "{{" in out and "}}" in out:
            raise ValueError("unresolved template variables.")
        return out


class PromptRegistry:
    """Versioned prompt store. Latest version wins per name; history retained."""

    def __init__(self) -> None:
        self._prompts: dict[str, list[PromptTemplate]] = {}

    def register(self, prompt: PromptTemplate) -> None:
        if not prompt.name or not prompt.version or not prompt.template:
            raise ValueError("name/version/template cannot be empty.")
        history = self._prompts.setdefault(prompt.name, [])
        if any(p.version == prompt.version for p in history):
            raise ValueError(f"duplicate version: {prompt.name}@{prompt.version}")
        history.append(prompt)

    def get(self, name: str, version: str | None = None) -> PromptTemplate:
        history = self._prompts.get(name)
        if not history:
            raise KeyError(f"unknown prompt: {name}")
        if version is None:
            return history[-1]
        for p in history:
            if p.version == version:
                return p
        raise KeyError(f"unknown version: {name}@{version}")

    def list(self) -> tuple[str, ...]:
        return tuple(sorted(self._prompts))


DEFAULT_ANALYSIS_PROMPT = PromptTemplate(
    name="financial_analysis",
    version="v1",
    template=(
        "Instrument: {{instrument}}\nHorizon: {{horizon}}\n"
        "Expected return: {{expected_return}}\nEvidence: {{evidence}}\n"
        "Respond with thesis, risks, and candidate action. "
        "Every factual claim must cite [evidence_id]."
    ),
)
