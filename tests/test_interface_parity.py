"""ADR-0006 gate: CLI map <-> TUI registry <-> runtime services agree.

One runtime, different presentations. No human surface outside CLI+TUI.
"""
import delta_tui.commands.terminal  # noqa: F401 (loads full surface)
from apps.api_contracts import CLI_MAP, check_parity
from delta_tui.commands.registry import lookup


def test_cli_commands_exist_in_tui_registry():
    for slash, _service in CLI_MAP.items():
        name = slash.strip("/ ")
        assert lookup(name) is not None, f"{slash} missing from TUI registry"


def test_cli_services_bound_to_runtime():
    services = {"markets.quote": 1, "portfolio.snapshot": 1, "risk.state": 1,
                "orders.stage": 1, "orders.submit": 1, "safety.kill": 1,
                "safety.unlock": 1, "system.status": 1}
    assert check_parity(services) == []
    for service in CLI_MAP.values():
        assert service in services, f"{service} unbound"


def test_no_web_surface_in_registry():
    for name in ("dashboard-web", "browser", "webapp", "gui"):
        assert lookup(name) is None
