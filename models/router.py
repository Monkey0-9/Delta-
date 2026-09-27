"""
Multi-model AI gateway with hot-swapping and role-based routing
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from delta.models.base_provider import (
    BaseModelProvider, ModelMessage, ModelResponse, ModelRole
)
from delta.core.registry import model_registry
from delta.core.config import Config, ModelConfig

logger = logging.getLogger(__name__)


class ModelRouter:
    """Router for multi-model AI gateway with hot-swapping"""
    
    def __init__(self, config: Config):
        self.config = config
        self.current_provider: Optional[BaseModelProvider] = None
        self.current_model_name: str = ""
        self.providers: Dict[str, BaseModelProvider] = {}
        self.role_routing: Dict[ModelRole, str] = {}
        
    async def initialize(self) -> None:
        """Initialize all configured model providers"""
        for model_config in self.config.models:
            if not model_config.enabled:
                continue
            
            try:
                provider = await self._create_provider(model_config)
                if provider:
                    self.providers[model_config.name] = provider
                    logger.info(f"Initialized model provider: {model_config.name}")
            except Exception as e:
                logger.error(f"Failed to initialize provider {model_config.name}: {e}")
        
        # Set default provider
        if self.config.models:
            default_model = self.config.models[0].name
            await self.switch_model(default_model)
    
    async def _create_provider(self, model_config: ModelConfig) -> Optional[BaseModelProvider]:
        """Create a provider instance from configuration"""
        provider_type = model_config.provider
        
        # Get provider class from registry
        provider_class = model_registry.get_provider_class(provider_type)
        if not provider_class:
            logger.error(f"Provider class not found: {provider_type}")
            return None
        
        # Build provider config
        provider_config = {
            "model": model_config.model,
            "endpoint": model_config.endpoint,
            "api_key": model_config.api_key_ref,
            **model_config.params
        }
        
        # Create and initialize provider
        provider = provider_class(provider_config)
        if await provider.initialize():
            return provider
        
        return None
    
    async def switch_model(self, model_name: str) -> bool:
        """Hot-swap to a different model"""
        if model_name not in self.providers:
            logger.error(f"Model not found: {model_name}")
            return False
        
        self.current_provider = self.providers[model_name]
        self.current_model_name = model_name
        logger.info(f"Switched to model: {model_name}")
        return True
    
    async def generate(self, messages: List[ModelMessage], 
                      model_name: Optional[str] = None,
                      role: Optional[ModelRole] = None,
                      params: Optional[Dict[str, Any]] = None) -> ModelResponse:
        """Generate a response using the specified or current model"""
        # Determine which provider to use
        provider = self.current_provider
        if model_name:
            if model_name in self.providers:
                provider = self.providers[model_name]
            else:
                logger.warning(f"Model {model_name} not found, using current")
        elif role and role in self.role_routing:
            routed_model = self.role_routing[role]
            if routed_model in self.providers:
                provider = self.providers[routed_model]
        
        if not provider:
            raise RuntimeError("No model provider available")
        
        return await provider.generate(messages, params)
    
    async def generate_stream(self, messages: List[ModelMessage],
                             model_name: Optional[str] = None,
                             role: Optional[ModelRole] = None,
                             params: Optional[Dict[str, Any]] = None):
        """Generate a streaming response"""
        provider = self.current_provider
        if model_name and model_name in self.providers:
            provider = self.providers[model_name]
        elif role and role in self.role_routing:
            routed_model = self.role_routing[role]
            if routed_model in self.providers:
                provider = self.providers[routed_model]
        
        if not provider:
            raise RuntimeError("No model provider available")
        
        async for chunk in provider.generate_stream(messages, params):
            yield chunk
    
    def set_role_routing(self, role: ModelRole, model_name: str) -> bool:
        """Set a model for a specific role"""
        if model_name not in self.providers:
            logger.error(f"Model not found for role routing: {model_name}")
            return False
        
        self.role_routing[role] = model_name
        logger.info(f"Set role routing: {role.value} -> {model_name}")
        return True
    
    def get_current_model(self) -> str:
        """Get the current model name"""
        return self.current_model_name
    
    def list_available_models(self) -> List[str]:
        """List all available model names"""
        return list(self.providers.keys())
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific model"""
        if model_name not in self.providers:
            return None
        
        provider = self.providers[model_name]
        capabilities = provider.get_capabilities()
        
        return {
            "name": model_name,
            "model": provider.get_model_name(),
            "endpoint": provider.get_endpoint(),
            "capabilities": {
                "max_context_tokens": capabilities.max_context_tokens,
                "supports_function_calling": capabilities.supports_function_calling,
                "supports_streaming": capabilities.supports_streaming,
                "supports_vision": capabilities.supports_vision,
                "estimated_cost_per_1k_tokens": capabilities.estimated_cost_per_1k_tokens
            },
            "initialized": provider.is_initialized()
        }
    
    async def health_check(self, model_name: Optional[str] = None) -> Dict[str, bool]:
        """Health check on one or all models"""
        if model_name:
            if model_name in self.providers:
                healthy = await self.providers[model_name].health_check()
                return {model_name: healthy}
            else:
                return {model_name: False}
        
        # Check all models
        results = {}
        for name, provider in self.providers.items():
            results[name] = await provider.health_check()
        
        return results
    
    def add_custom_provider(self, name: str, provider: BaseModelProvider) -> None:
        """Add a custom provider at runtime"""
        self.providers[name] = provider
        logger.info(f"Added custom provider: {name}")
    
    def remove_provider(self, name: str) -> bool:
        """Remove a provider"""
        if name in self.providers:
            if self.current_model_name == name:
                logger.warning(f"Cannot remove current provider: {name}")
                return False
            
            del self.providers[name]
            logger.info(f"Removed provider: {name}")
            return True
        
        return False
