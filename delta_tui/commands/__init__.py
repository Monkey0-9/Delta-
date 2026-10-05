"""Command package init — loads alias + terminal surfaces into the registry."""
from . import aliases  # noqa: F401
from . import terminal  # noqa: F401
from .registry import REGISTRY, lookup  # noqa: F401
from .ux import dispatch, fuzzy_rank, nl_to_action, unknown_guidance  # noqa: F401
