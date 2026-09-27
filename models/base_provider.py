"""
Abstract base interface for AI model providers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class ModelRole(Enum):
    """Model role for task routing"""
    GENERAL = "general"
    QUANT_STRATEGY = "quant_strategy"
    RISK_ANALYSIS = "risk_analysis"
    REGULATORY = "regulatory"
    CODE_GENERATION = "code_generation"
    NEWS_ANALYSIS = "news_analysis"


@dataclass
class ModelMessage:
    """Standardized message format"""
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelResponse:
    """Standardized model response"""
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    latency_ms: float
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ModelCapabilities:
    """Model capability description"""
    max_context_tokens: int
    supports_function_calling: bool
    supports_streaming: bool
    supports_vision: bool
    estimated_cost_per_1k_tokens: float


class BaseModelProvider(ABC):
    """Abstract base class for all AI model providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model", "unknown")
        self.endpoint = config.get("endpoint", "")
        self.api_key = config.get("api_key", "")
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the provider connection"""
        pass
    
    @abstractmethod
    async def generate(self, messages: List[ModelMessage], 
                      params: Optional[Dict[str, Any]] = None) -> ModelResponse:
        """Generate a response from the model"""
        pass
    
    @abstractmethod
    async def generate_stream(self, messages: List[ModelMessage],
                            params: Optional[Dict[str, Any]] = None):
        """Generate a streaming response"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> ModelCapabilities:
        """Get model capabilities"""
        pass
    
    @abstractmethod
    def supports_function_calling(self) -> bool:
        """Check if model supports function calling"""
        pass
    
    def is_initialized(self) -> bool:
        """Check if provider is initialized"""
        return self._initialized
    
    def get_model_name(self) -> str:
        """Get the model name"""
        return self.model_name
    
    def get_endpoint(self) -> str:
        """Get the endpoint URL"""
        return self.endpoint
    
    async def health_check(self) -> bool:
        """Perform a health check on the provider"""
        try:
            test_messages = [ModelMessage(role="user", content="Hello")]
            response = await self.generate(test_messages)
            return response.content is not None
        except Exception:
            return False
    
    def validate_config(self) -> bool:
        """Validate the provider configuration"""
        required_fields = ["model", "endpoint"]
        for field in required_fields:
            if field not in self.config:
                return False
        return True


class OpenAICompatibleProvider(BaseModelProvider):
    """Base class for OpenAI-compatible API providers"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.organization = config.get("organization", None)
    
    def get_default_params(self) -> Dict[str, Any]:
        """Get default generation parameters"""
        return {
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }
    
    def supports_function_calling(self) -> bool:
        """OpenAI-compatible providers typically support function calling"""
        return True


class LocalProvider(BaseModelProvider):
    """Base class for local model providers (Ollama, vLLM)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 11434)
    
    def supports_function_calling(self) -> bool:
        """Local providers may have limited function calling support"""
        return False
    
    def get_endpoint(self) -> str:
        """Construct endpoint from host and port"""
        return f"http://{self.host}:{self.port}"
