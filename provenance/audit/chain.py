from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class AuditRecord:
    sequence: int
    record_type: str
    record_id: str
    payload_hash: str
    previous_hash: str
    record_hash: str
    timestamp: datetime


class AuditChain:
    """
    Append-only hash chain for provenance/audit records.

    Each record commits to:
        sequence
        record type
        record ID
        payload hash
        previous record hash
        timestamp

    Tampering with any record breaks the chain.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    @property
    def records(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

    @property
    def head_hash(self) -> str:
        if not self._records:
            return self.GENESIS_HASH

        return self._records[-1].record_hash

    def _canonical_record_payload(
        self,
        *,
        sequence: int,
        record_type: str,
        record_id: str,
        payload_hash: str,
        previous_hash: str,
        timestamp: datetime,
    ) -> bytes:
        payload = {
            "sequence": sequence,
            "record_type": record_type,
            "record_id": record_id,
            "payload_hash": payload_hash,
            "previous_hash": previous_hash,
            "timestamp": timestamp.isoformat(),
        }

        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def append(
        self,
        *,
        record_type: str,
        record_id: str,
        payload_hash: str,
        timestamp: datetime | None = None,
    ) -> AuditRecord:
        if not record_type.strip():
            raise ValueError("record_type cannot be empty.")

        if not record_id.strip():
            raise ValueError("record_id cannot be empty.")

        if not payload_hash.strip():
            raise ValueError("payload_hash cannot be empty.")

        resolved_timestamp = (
            timestamp
            if timestamp is not None
            else _utc_now()
        )

        if resolved_timestamp.tzinfo is None:
            resolved_timestamp = resolved_timestamp.replace(
                tzinfo=timezone.utc
            )
        else:
            resolved_timestamp = resolved_timestamp.astimezone(
                timezone.utc
            )

        sequence = len(self._records)

        previous_hash = self.head_hash

        canonical = self._canonical_record_payload(
            sequence=sequence,
            record_type=record_type,
            record_id=record_id,
            payload_hash=payload_hash,
            previous_hash=previous_hash,
            timestamp=resolved_timestamp,
        )

        record_hash = hashlib.sha256(canonical).hexdigest()

        record = AuditRecord(
            sequence=sequence,
            record_type=record_type,
            record_id=record_id,
            payload_hash=payload_hash,
            previous_hash=previous_hash,
            record_hash=record_hash,
            timestamp=resolved_timestamp,
        )

        self._records.append(record)

        return record

    def verify(self) -> bool:
        """
        Verify the complete chain.

        Returns False instead of raising for integrity failure.
        """

        previous_hash = self.GENESIS_HASH

        for expected_sequence, record in enumerate(self._records):
            if record.sequence != expected_sequence:
                return False

            if record.previous_hash != previous_hash:
                return False

            canonical = self._canonical_record_payload(
                sequence=record.sequence,
                record_type=record.record_type,
                record_id=record.record_id,
                payload_hash=record.payload_hash,
                previous_hash=record.previous_hash,
                timestamp=record.timestamp,
            )

            expected_hash = hashlib.sha256(
                canonical
            ).hexdigest()

            if record.record_hash != expected_hash:
                return False

            previous_hash = record.record_hash

        return True

    def is_valid(self) -> bool:
        return self.verify()

    def __len__(self) -> int:
        return len(self._records)