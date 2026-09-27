from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True, init=False)
class Evidence:
    """
    Immutable provenance evidence.

    Evidence is content-addressable: identical logical evidence produces
    the same SHA-256 content hash.
    """

    evidence_id: UUID
    source: str
    observation: str
    timestamp: datetime
    confidence: Decimal
    metadata: tuple[tuple[str, str], ...]

    def __init__(
        self,
        source: str,
        observation: str | None = None,
        *,
        claim: str | None = None,
        content: str | None = None,
        value: Any | None = None,
        timestamp: datetime | None = None,
        confidence: Decimal | float | int = Decimal("1"),
        evidence_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if not source or not source.strip():
            raise ValueError("Evidence source cannot be empty.")

        resolved = (
            observation
            if observation is not None
            else claim
            if claim is not None
            else content
            if content is not None
            else None
        )

        if resolved is None and value is not None:
            resolved = str(value)

        if resolved is None or not str(resolved).strip():
            raise ValueError(
                "Evidence requires observation, claim, content, or value."
            )

        resolved_confidence = Decimal(str(confidence))

        if not Decimal("0") <= resolved_confidence <= Decimal("1"):
            raise ValueError(
                "Evidence confidence must be between 0 and 1."
            )

        metadata_items: list[tuple[str, str]] = []

        if metadata:
            metadata_items.extend(
                (str(k), str(v))
                for k, v in sorted(metadata.items())
            )

        for key, val in sorted(kwargs.items()):
            metadata_items.append((str(key), str(val)))

        object.__setattr__(
            self,
            "evidence_id",
            evidence_id or uuid4(),
        )
        object.__setattr__(
            self,
            "source",
            source.strip(),
        )
        object.__setattr__(
            self,
            "observation",
            str(resolved).strip(),
        )
        object.__setattr__(
            self,
            "timestamp",
            _utc(timestamp),
        )
        object.__setattr__(
            self,
            "confidence",
            resolved_confidence,
        )
        object.__setattr__(
            self,
            "metadata",
            tuple(metadata_items),
        )

    @property
    def id(self) -> UUID:
        return self.evidence_id

    @property
    def claim(self) -> str:
        return self.observation

    @property
    def content(self) -> str:
        return self.observation

    @property
    def value(self) -> str:
        return self.observation

    def metadata_dict(self) -> dict[str, str]:
        return dict(self.metadata)

    def canonical_payload(self) -> dict[str, Any]:
        """
        Return the deterministic representation used for hashing.

        IMPORTANT:
        evidence_id is deliberately excluded.

        Two independently-created Evidence objects containing the same
        source/observation/timestamp/etc. therefore have the same hash.
        """

        return {
            "source": self.source,
            "observation": self.observation,
            "timestamp": self.timestamp.isoformat(),
            "confidence": str(self.confidence),
            "metadata": [
                [key, value]
                for key, value in self.metadata
            ],
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    def content_hash(self) -> str:
        """
        Return the SHA-256 hash of canonical evidence content.

        Always returns exactly 64 hexadecimal characters.
        """

        return hashlib.sha256(
            self.canonical_bytes()
        ).hexdigest()