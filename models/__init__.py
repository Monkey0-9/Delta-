"""
Multi-model AI gateway with plugin support
"""

try:
    from delta.models.router import ModelRouter
except Exception:
    try:
        from models.router import ModelRouter
    except Exception:
        ModelRouter = None  # type: ignore[assignment,misc]

try:
    from delta.models.base_provider import (
        BaseModelProvider,
        ModelMessage,
        ModelResponse,
    )
except Exception:
    try:
        from models.base_provider import (
            BaseModelProvider,
            ModelMessage,
            ModelResponse,
        )
    except Exception:
        BaseModelProvider = None  # type: ignore[assignment,misc]
        ModelMessage = None  # type: ignore[assignment,misc]
        ModelResponse = None  # type: ignore[assignment,misc]

__all__ = ["ModelRouter", "BaseModelProvider", "ModelMessage", "ModelResponse"]
