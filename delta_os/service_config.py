"""DELTA OS — Durable Service Configuration Subsystem.

Provides atomic, filesystem-synced, schema-validated configuration management
for the 24/7 background sentinel daemon and quantitative runtime.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class ConfigurationCorruptError(ValueError):
    """Raised when configuration file contains invalid JSON, invalid keys, or out-of-bound values."""
    pass


DEFAULT_SERVICE_CONFIG: Dict[str, Any] = {
    "revision": 1,
    "updated_at": "2026-01-01T00:00:00+00:00",
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

RESTART_REQUIRED_KEYS = {"daily_reset_utc", "equity_source"}


def get_config_path() -> Path:
    """Resolve authoritative path to service_config.json."""
    base = Path(os.environ.get("DELTA_HOME", str(Path.home() / ".delta")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "service_config.json"


def normalize_key(key: str) -> str:
    """Map user-facing aliases to canonical schema keys."""
    k = key.strip().lower()
    return KEY_ALIASES.get(k, k)


def validate_config_dict(data: Any) -> Dict[str, Any]:
    """Validate raw dictionary against service configuration schema.
    
    Raises:
        ConfigurationCorruptError: If structure or values violate schema constraints.
    """
    if not isinstance(data, dict):
        raise ConfigurationCorruptError("Configuration root must be a JSON dictionary object.")

    validated: Dict[str, Any] = dict(DEFAULT_SERVICE_CONFIG)

    for k, v in data.items():
        if k in ("revision", "updated_at"):
            if k == "revision":
                if not isinstance(v, int) or v < 1:
                    raise ConfigurationCorruptError(f"Field 'revision' must be positive integer, got {v!r}")
                validated["revision"] = v
            elif k == "updated_at":
                if not isinstance(v, str):
                    raise ConfigurationCorruptError(f"Field 'updated_at' must be ISO timestamp string, got {v!r}")
                validated["updated_at"] = v
            continue

        canon_k = normalize_key(k)
        if canon_k not in DEFAULT_SERVICE_CONFIG:
            raise ConfigurationCorruptError(f"Unknown configuration key: '{k}'")

        if canon_k in NUMERIC_BOUNDS:
            try:
                num_val = float(v)
            except (ValueError, TypeError):
                raise ConfigurationCorruptError(f"Value for '{canon_k}' must be numeric, got {v!r}")
            low, high = NUMERIC_BOUNDS[canon_k]
            if not (low <= num_val <= high):
                raise ConfigurationCorruptError(
                    f"Value {num_val} for '{canon_k}' out of bounds [{low}, {high}]"
                )
            validated[canon_k] = num_val
        elif canon_k == "alert_channels":
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise ConfigurationCorruptError(f"Value for '{canon_k}' must be a list of strings, got {v!r}")
            validated[canon_k] = list(v)
        elif canon_k == "log_level":
            str_val = str(v).upper().strip()
            if str_val not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
                raise ConfigurationCorruptError(f"Invalid log_level '{v}'. Must be DEBUG, INFO, WARNING, ERROR, CRITICAL")
            validated[canon_k] = str_val
        elif canon_k == "daily_reset_utc":
            str_val = str(v).strip()
            parts = str_val.split(":")
            if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()) or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
                raise ConfigurationCorruptError(f"daily_reset_utc must be HH:MM 24-hour UTC format, got {v!r}")
            validated[canon_k] = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        elif canon_k == "equity_source":
            if not isinstance(v, str) or not v.strip():
                raise ConfigurationCorruptError(f"Field 'equity_source' must be non-empty string, got {v!r}")
            validated[canon_k] = v.strip()

    return validated


def load_config() -> Dict[str, Any]:
    """Load persisted configuration, validating schema strictly.
    
    Raises:
        ConfigurationCorruptError: If configuration file is corrupt or invalid.
    """
    p = get_config_path()
    if not p.exists():
        return dict(DEFAULT_SERVICE_CONFIG)

    try:
        content = p.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as exc:
        raise ConfigurationCorruptError(f"Corrupt configuration file at {p}: {exc}") from exc

    return validate_config_dict(data)


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


def set_value(
    key: str,
    value: Any,
    auth_token: Optional[str] = None,
    role: Optional[Any] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate, authorize, and persist a service configuration parameter.
    
    Risk-loosening changes (e.g. increasing max_dd_pct) require explicit authorization
    via DELTA_UNLOCK_TOKEN or RISK_OFFICER role.
    """
    canon_k = normalize_key(key)
    if canon_k not in DEFAULT_SERVICE_CONFIG:
        return False, f"Unknown configuration key: '{key}'. Valid keys: {', '.join(sorted(DEFAULT_SERVICE_CONFIG.keys()))}", {}

    # Load current configuration
    current_cfg = load_config()

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

        # Risk-loosening check: increasing max_dd_pct allows greater drawdown
        if canon_k == "max_dd_pct":
            current_max_dd = float(current_cfg.get("max_dd_pct", 2.0))
            if cast_val > current_max_dd:
                valid_token = os.environ.get("DELTA_UNLOCK_TOKEN")
                is_auth = False
                if valid_token and auth_token and auth_token == valid_token:
                    is_auth = True
                elif role and str(getattr(role, "name", role)).upper() in ("RISK_OFFICER", "ADMIN"):
                    is_auth = True

                if not is_auth:
                    return (
                        False,
                        f"Authorization required for risk-loosening change: increasing max_dd_pct from "
                        f"{current_max_dd}% to {cast_val}% requires DELTA_UNLOCK_TOKEN or RISK_OFFICER role.",
                        {},
                    )

    elif canon_k == "alert_channels":
        if isinstance(value, str):
            cast_val = [c.strip() for c in value.split(",") if c.strip()]
        elif not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            return False, f"Value for '{canon_k}' must be a list of strings or comma-separated string", {}
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
    elif canon_k == "equity_source":
        str_val = str(value).strip()
        if not str_val:
            return False, "equity_source cannot be empty", {}
        cast_val = str_val

    # Apply update and bump revision
    current_cfg[canon_k] = cast_val
    current_cfg["revision"] = int(current_cfg.get("revision", 1)) + 1
    current_cfg["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_config(current_cfg)

    msg_suffix = " (RESTART_REQUIRED for daemon to apply)" if canon_k in RESTART_REQUIRED_KEYS else " (hot-reloaded)"
    return True, f"Updated {canon_k} = {cast_val}.{msg_suffix}", current_cfg


def unset_value(
    key: str,
    auth_token: Optional[str] = None,
    role: Optional[Any] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Reset a service configuration parameter to its canonical default."""
    canon_k = normalize_key(key)
    if canon_k not in DEFAULT_SERVICE_CONFIG:
        return False, f"Unknown configuration key: '{key}'", {}

    default_val = DEFAULT_SERVICE_CONFIG[canon_k]
    return set_value(canon_k, default_val, auth_token=auth_token, role=role)
