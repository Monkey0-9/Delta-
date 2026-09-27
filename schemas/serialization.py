"""Canonical binary codec: versioned MessagePack envelope with integrity hash."""
from __future__ import annotations

import hashlib
import json

CODEC_VERSION = "msgpack.v1"


def pack(payload: dict) -> bytes:
    import msgpack

    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    envelope = {
        "v": CODEC_VERSION,
        "sha": hashlib.sha256(body).hexdigest(),
        "body": body.decode("utf-8"),
    }
    return msgpack.packb(envelope, use_bin_type=True)


def unpack(blob: bytes) -> dict:
    import msgpack

    envelope = msgpack.unpackb(blob, raw=False)
    if envelope.get("v") != CODEC_VERSION:
        raise ValueError(f"unsupported codec version: {envelope.get('v')!r}.")
    body = envelope["body"].encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    if digest != envelope["sha"]:
        raise ValueError("integrity check failed.")
    return json.loads(body)
