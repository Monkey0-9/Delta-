from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CredentialReference:
    """
    Reference to credentials without storing the secret itself.
    """

    provider: str
    account_id: str
    key_name: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider cannot be empty")

        if not self.account_id.strip():
            raise ValueError("account_id cannot be empty")

        if not self.key_name.strip():
            raise ValueError("key_name cannot be empty")


class CredentialStore:
    """
    Interface boundary.

    Production implementation should be backed by an OS/cloud
    secret manager. The trading agent receives references, never
    raw secrets.
    """

    def __init__(self) -> None:
        self._references: dict[str, CredentialReference] = {}

    def register(
        self,
        reference: CredentialReference,
    ) -> None:
        if reference.key_name in self._references:
            raise ValueError(
                f"Credential reference already exists: {reference.key_name}"
            )

        self._references[reference.key_name] = reference

    def get_reference(
        self,
        key_name: str,
    ) -> CredentialReference:
        try:
            return self._references[key_name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown credential reference: {key_name}"
            ) from exc