"""
Configuration management with plugin support and environment variable loading
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class ExecutionMode(Enum):
    MANUAL = "manual"
    AUTOMATION = "automation"
    HALTED = "halted"


class Theme(Enum):
    BLOOMBERG_AMBER = "bloomberg_amber"
    TOKYO_NIGHT = "tokyo_night"
    MATRIX_TERMINAL = "matrix_terminal"
    MONOKAI_PRO = "monokai_pro"


@dataclass
class ModelConfig:
    name: str
    provider: str
    endpoint: str
    model: str
    api_key_ref: Optional[str] = None
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerConfig:
    name: str
    type: str
    environment: str = "paper"
    credentials_ref: Optional[str] = None
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataProviderConfig:
    name: str
    provider: str
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskConfig:
    max_position_pct: float = 5.0
    max_leverage: float = 1.5
    daily_drawdown_limit: float = 2.0
    kelly_fraction: float = 0.25
    var_confidence: float = 0.99


@dataclass
class Config:
    """Central configuration schema with plugin support"""
    
    # System
    version: str = "2.0.0"
    workspace: str = "EQUITIES-ALPHA"
    execution_mode: ExecutionMode = ExecutionMode.MANUAL
    theme: Theme = Theme.MONOKAI_PRO
    kill_switch_armed: bool = True
    
    # Paths
    config_dir: Path = field(default_factory=lambda: Path.home() / ".delta")
    vault_path: Path = field(default_factory=lambda: Path.home() / ".delta" / "vault.bin")
    plugin_dir: Path = field(default_factory=lambda: Path.home() / ".delta" / "plugins")
    audit_log_path: Path = field(default_factory=lambda: Path.home() / ".delta" / "audit.log")
    
    # Providers
    models: List[ModelConfig] = field(default_factory=list)
    brokers: List[BrokerConfig] = field(default_factory=list)
    data_providers: List[DataProviderConfig] = field(default_factory=list)
    
    # Risk
    risk: RiskConfig = field(default_factory=RiskConfig)
    
    # Anti-tilt
    anti_tilt_enabled: bool = True
    consecutive_loss_limit: int = 3
    cooldown_minutes: int = 30
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file"""
        if config_path is None:
            config_path = Path.home() / ".delta" / "config.yaml"
        
        if not config_path.exists():
            return cls()  # Return default config
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create Config from dictionary"""
        config = cls()
        
        # System
        if "version" in data:
            config.version = data["version"]
        if "workspace" in data:
            config.workspace = data["workspace"]
        if "execution_mode" in data:
            config.execution_mode = ExecutionMode(data["execution_mode"])
        if "theme" in data:
            config.theme = Theme(data["theme"])
        if "kill_switch_armed" in data:
            config.kill_switch_armed = data["kill_switch_armed"]
        
        # Paths
        if "config_dir" in data:
            config.config_dir = Path(data["config_dir"])
        if "vault_path" in data:
            config.vault_path = Path(data["vault_path"])
        if "plugin_dir" in data:
            config.plugin_dir = Path(data["plugin_dir"])
        if "audit_log_path" in data:
            config.audit_log_path = Path(data["audit_log_path"])
        
        # Models
        if "models" in data:
            config.models = [ModelConfig(**m) for m in data["models"]]
        
        # Brokers
        if "brokers" in data:
            config.brokers = [BrokerConfig(**b) for b in data["brokers"]]
        
        # Data providers
        if "data_providers" in data:
            config.data_providers = [DataProviderConfig(**d) for d in data["data_providers"]]
        
        # Risk
        if "risk" in data:
            config.risk = RiskConfig(**data["risk"])
        
        # Anti-tilt
        if "anti_tilt_enabled" in data:
            config.anti_tilt_enabled = data["anti_tilt_enabled"]
        if "consecutive_loss_limit" in data:
            config.consecutive_loss_limit = data["consecutive_loss_limit"]
        if "cooldown_minutes" in data:
            config.cooldown_minutes = data["cooldown_minutes"]
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Config to dictionary"""
        return {
            "version": self.version,
            "workspace": self.workspace,
            "execution_mode": self.execution_mode.value,
            "theme": self.theme.value,
            "kill_switch_armed": self.kill_switch_armed,
            "config_dir": str(self.config_dir),
            "vault_path": str(self.vault_path),
            "plugin_dir": str(self.plugin_dir),
            "audit_log_path": str(self.audit_log_path),
            "models": [m.__dict__ for m in self.models],
            "brokers": [b.__dict__ for b in self.brokers],
            "data_providers": [d.__dict__ for d in self.data_providers],
            "risk": self.risk.__dict__,
            "anti_tilt_enabled": self.anti_tilt_enabled,
            "consecutive_loss_limit": self.consecutive_loss_limit,
            "cooldown_minutes": self.cooldown_minutes,
        }
    
    def save(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to YAML file"""
        if config_path is None:
            config_path = self.config_dir / "config.yaml"
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        (self.plugin_dir / "models").mkdir(parents=True, exist_ok=True)
        (self.plugin_dir / "brokers").mkdir(parents=True, exist_ok=True)
        (self.plugin_dir / "data").mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def init_default(cls) -> "Config":
        """Initialize default configuration with free tier options"""
        config = cls()
        config.ensure_directories()
        
        # Add default free tier models
        config.models = [
            ModelConfig(
                name="local-qwen",
                provider="ollama",
                endpoint="http://localhost:11434",
                model="qwen2.5:7b",
                enabled=True
            ),
            ModelConfig(
                name="groq",
                provider="openai-compatible",
                endpoint="https://api.groq.com/openai/v1",
                model="llama3-70b-8192",
                api_key_ref="groq_api_key",
                enabled=True
            ),
            ModelConfig(
                name="huggingface",
                provider="huggingface",
                endpoint="https://api-inference.huggingface.co",
                model="mistralai/Mistral-7B-Instruct-v0.2",
                api_key_ref="huggingface_token",
                enabled=True
            )
        ]
        
        # Add default brokers
        config.brokers = [
            BrokerConfig(
                name="paper-engine",
                type="paper",
                environment="paper",
                enabled=True
            ),
            BrokerConfig(
                name="alpaca-paper",
                type="alpaca",
                environment="paper",
                credentials_ref="alpaca_keys",
                enabled=True
            )
        ]
        
        # Add default data providers
        config.data_providers = [
            DataProviderConfig(
                name="yahoo-finance",
                provider="yahoo",
                enabled=True
            ),
            DataProviderConfig(
                name="fred",
                provider="fred",
                params={"api_key_ref": "fred_api_key"},
                enabled=True
            ),
            DataProviderConfig(
                name="google-news",
                provider="google_news",
                enabled=True
            )
        ]
        
        config.save()
        return config


def get_config() -> Config:
    """Get global configuration instance"""
    return Config.load()
