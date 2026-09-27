from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json


@dataclass(frozen=True, slots=True)
class ReproducibilityManifest:

    git_commit: str
    dataset_hash: str
    model_hash: str
    strategy_hash: str
    config_hash: str
    seed: int
    environment_hash: str

    @property
    def fingerprint(self) -> str:

        payload = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            payload.encode()
        ).hexdigest()

    def verify(self, fingerprint: str) -> bool:
        """Recompute and compare — detects any manifest tampering."""
        import hmac

        return hmac.compare_digest(self.fingerprint, fingerprint)

    @classmethod
    def from_parts(
        cls,
        *,
        git_commit: str,
        dataset_hash: str,
        model_hash: str,
        strategy_hash: str,
        config_hash: str,
        seed: int,
        environment_hash: str = "",
    ) -> ReproducibilityManifest:
        if seed < 0:
            raise ValueError("seed must be non-negative.")
        for label, value in (
            ("dataset_hash", dataset_hash),
            ("model_hash", model_hash),
            ("strategy_hash", strategy_hash),
            ("config_hash", config_hash),
        ):
            if not value.strip():
                raise ValueError(f"{label} required.")
        return cls(
            git_commit=git_commit or "unknown",
            dataset_hash=dataset_hash,
            model_hash=model_hash,
            strategy_hash=strategy_hash,
            config_hash=config_hash,
            seed=seed,
            environment_hash=environment_hash or _environment_hash(),
        )


def _environment_hash() -> str:
    import platform
    import sys

    payload = json.dumps(
        {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()