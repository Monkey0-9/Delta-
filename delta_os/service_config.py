"""DELTA OS — Durable Service Configuration Subsystem.

Provides atomic, filesystem-synced, schema-validated configuration management
for the 24/7 background sentinel daemon and quantitative runtime.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_SERVICE_CONFIG: Dict[str, Any] = {
    "max_dd_pct": 2.0,            # Max portfolio daily drawdown limit % (0.1 to 20.0)
    "interval_s": 3.0,            # Surveillance loop interval seconds (0.5 to 60.0)
    "alert_channels": [],         # Configured webhook/alert sinks
    "log_level": "INFO",          # Logging verbosity: DEBUG, INFO, WARNING, ERROR
    "daily_reset_utc": "00:00",   # Daily drawdown reset time in UTC (HH:MM)
    "equity_source": "paper_ledger", # Canonical portfolio equity provider
}

KEY_ALIASES: Dict[str, str] = {
    "max_dd": "max_dd_pct",
    "drawdown": "max_dd_pct",
    "interval": "interval_s",
    "reset": "daily_reset_utc",
    "source": "equity_source",
    "level": "log_level",
}

NUMERIC_BOUNDS: Dict[str, Tuple[float, float]] = {
    "max_dd_pct": (0.1, 20.0),
    "interval_s": (0.5, 60.0),
}


def get_config_path() -> Path:
    """Resolve authoritative path to service_config.json."""
    base = Path(os.environ.get("DELTA_HOME", str(Path.home() / ".delta")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "service_config.json"


def normalize_key(key: str) -> str:
    """Map user-facing aliases to canonical schema keys."""
    k = key.strip().lower()
    return KEY_ALIASES.get(k, k)


def load_config() -> Dict[str, Any]:
    """Load persisted configuration, falling back to canonical defaults."""
    cfg = dict(DEFAULT_SERVICE_CONFIG)
    p = get_config_path()
    if not p.exists():
        return cfg
    try:
        content = p.read_text(encoding="utf-8")
        data = json.loads(content)
        if isinstance(data, dict):
            for k, v in data.items():
                canon_k = normalize_key(k)
                if canon_k in DEFAULT_SERVICE_CONFIG:
                    cfg[canon_k] = v
    except Exception:
        # Corrupt or unreadable file: return safe defaults
        pass
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """Save configuration atomically with fsync and restricted file mode (0o600)."""
    p = get_config_path()
    parent = p.parent
    parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(cfg, indent=2, sort_keys=True)
    # Atomic write via temp file in the same filesystem directory
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(parent), prefix=".service_cfg_tmp_")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        # Set restrictive permissions (user read/write only)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, str(p))
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def get_value(key: Optional[str] = None) -> Any:
    """Get a specific configuration parameter or entire configuration dictionary."""
    cfg = load_config()
    if key is None:
        return cfg
    canon_k = normalize_key(key)
    if canon_k not in DEFAULT_SERVICE_CONFIG:
        return None
    return cfg.get(canon_k, DEFAULT_SERVICE_CONFIG.get(canon_k))


def set_value(key: str, value: Any) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate, typecast, and persist a service configuration parameter."""
    canon_k = normalize_key(key)
    if canon_k not in DEFAULT_SERVICE_CONFIG:
        return False, f"Unknown configuration key: '{key}'. Valid keys: {', '.join(sorted(DEFAULT_SERVICE_CONFIG.keys()))}", {}

    # Typecasting and validation
    cast_val = value
    if canon_k in NUMERIC_BOUNDS:
        try:
            cast_val = float(value)
        except (ValueError, TypeError):
            return False, f"Value for '{canon_k}' must be a valid number, got {value!r}", {}
        low, high = NUMERIC_BOUNDS[canon_k]
        if not (low <= cast_val <= high):
            return False, f"Value {cast_val} for '{canon_k}' out of bounds. Permitted range: [{low}, {high}]", {}
    elif canon_k == "alert_channels":
        if isinstance(value, str):
            cast_val = [c.strip() for c in value.split(",") if c.strip()]
        elif not isinstance(value, list):
            return False, f"Value for '{canon_k}' must be a list or comma-separated string", {}
    elif canon_k == "log_level":
        str_val = str(value).upper().strip()
        if str_val not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            return False, f"Invalid log_level '{value}'. Permitted: DEBUG, INFO, WARNING, ERROR, CRITICAL", {}
        cast_val = str_val
    elif canon_k == "daily_reset_utc":
        str_val = str(value).strip()
        parts = str_val.split(":")
        if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()) or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
            return False, f"daily_reset_utc must be in HH:MM 24-hour UTC format, got {value!r}", {}
        cast_val = f"{int(parts[0]):02d}:{int(parts[1]):02d}"

    cfg = load_config()
    cfg[canon_k] = cast_val
    save_config(cfg)
    return True, f"Updated {canon_k} = {cast_val}", cfg


def unset_value(key: str) -> Tuple[bool, str, Dict[str, Any]]:
    """Reset a service configuration parameter to its canonical default."""
    canon_k = normalize_key(key)
    if canon_k not in DEFAULT_SERVICE_CONFIG:
        return False, f"Unknown configuration key: '{key}'", {}

    cfg = load_config()
    default_val = DEFAULT_SERVICE_CONFIG[canon_k]
    cfg[canon_k] = default_val
    save_config(cfg)
    return True, f"Reset {canon_k} to default ({default_val})", cfg
