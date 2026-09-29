"""
Model class registry for DELTA OS model zoo.

Maps string names to estimator classes with lazy instantiation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Type


class ModelRegistry:
    """
    Named estimator-class registry.

    Features:
    - Register estimator classes by name
    - Instantiate via ``create``
    - Sorted model listing
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._models: Dict[str, Type[Any]] = {}

    def register(self, name: str, cls: Type[Any]) -> None:
        """
        Register an estimator class.

        Args:
            name: Model identifier
            cls: Estimator class (not instance)

        Raises:
            ValueError: If name invalid, cls not a class, or duplicate.
        """
        if not name or not isinstance(name, str):
            raise ValueError("Model name must be a non-empty string")
        if not isinstance(cls, type):
            raise ValueError(f"Model '{name}' cls must be a class")
        if name in self._models:
            raise ValueError(f"Model '{name}' already registered")
        self._models[name] = cls

    def get(self, name: str) -> Type[Any]:
        """
        Get a registered estimator class.

        Args:
            name: Model identifier

        Returns:
            Registered class

        Raises:
            KeyError: If model is not registered.
        """
        try:
            return self._models[name]
        except KeyError:
            raise KeyError(f"Model '{name}' not found") from None

    def has(self, name: str) -> bool:
        """
        Check whether a model is registered.

        Args:
            name: Model identifier

        Returns:
            True if registered, False otherwise.
        """
        return name in self._models

    def create(self, name: str, **kw: Any) -> Any:
        """
        Instantiate a registered model.

        Args:
            name: Model identifier
            **kw: Constructor keyword arguments

        Returns:
            Estimator instance

        Raises:
            KeyError: If model is not registered.
        """
        return self.get(name)(**kw)

    def list_models(self) -> List[str]:
        """
        List registered model names.

        Returns:
            Sorted list of model names.
        """
        return sorted(self._models.keys())

    def unregister(self, name: str) -> bool:
        """
        Remove a model registration.

        Args:
            name: Model identifier

        Returns:
            True if removed, False if absent.
        """
        return self._models.pop(name, None) is not None


__all__ = [
    "ModelRegistry",
]
