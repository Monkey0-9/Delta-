from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SchemaVersion:
    name: str
    major: int
    minor: int

    @property
    def value(self) -> str:
        return f"{self.name}.v{self.major}.{self.minor}"

    def __str__(self) -> str:
        return self.value