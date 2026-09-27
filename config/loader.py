"""Environment configuration loader: base.yaml + env overlay.

Risk semantics: most-restrictive wins — numeric risk limits take the MINIMUM
of base and overlay. Everything else: overlay wins. Unknown envs rejected.
"""
from __future__ import annotations

import pathlib

ENVS = ("research", "simulation", "paper", "copilot", "supervised")

_RISK_MIN_KEYS = (
    "max_order_qty", "max_order_notional", "max_intraday_position",
    "max_position_notional",
    "max_gross_exposure", "max_leverage", "price_tolerance_bps", "stale_data_ttl_s",
)

_CONFIG_DIR = pathlib.Path(__file__).resolve().parent


def _read_yaml(path: pathlib.Path) -> dict:
    import yaml

    with open(path, encoding="utf-8") as fh:
        return dict(yaml.safe_load(fh) or {})


def load_config(env: str, config_dir: str | pathlib.Path = _CONFIG_DIR) -> dict:
    if env not in ENVS:
        raise ValueError(f"unknown env: {env}. Choose from {ENVS}.")
    base_file = pathlib.Path(config_dir) / "base.yaml"
    if not base_file.exists():
        raise ValueError(f"missing base config: {base_file}.")
    merged = _read_yaml(base_file)
    overlay_file = pathlib.Path(config_dir) / ("paper_env.yaml" if env == "paper" else f"{env}.yaml")
    overlay = _read_yaml(overlay_file) if overlay_file.exists() else {}
    for section, values in overlay.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section] = {**merged[section], **values}
        else:
            merged[section] = values
    base_risk = _read_yaml(base_file).get("risk", {})
    env_risk = overlay.get("risk", {})
    if isinstance(env_risk, dict):
        merged_risk = dict(merged.get("risk", {}))
        for key in _RISK_MIN_KEYS:
            if key in base_risk and key in env_risk:
                merged_risk[key] = min(base_risk[key], env_risk[key])
        merged["risk"] = merged_risk
    merged["env"] = env
    return merged
