"""
Registry system for managing model providers and broker adapters
"""

from typing import Dict, Type, Optional, List, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for AI model providers"""
    
    def __init__(self):
        self._providers: Dict[str, Type] = {}
        self._instances: Dict[str, Any] = {}
    
    def register_provider(self, name: str, provider_class: Type) -> None:
        """Register a model provider class"""
        self._providers[name] = provider_class
        logger.info(f"Registered model provider: {name}")
    
    def get_provider_class(self, name: str) -> Optional[Type]:
        """Get a registered provider class"""
        return self._providers.get(name)
    
    def create_provider(self, name: str, config: Dict[str, Any]) -> Optional[Any]:
        """Create an instance of a provider"""
        provider_class = self.get_provider_class(name)
        if provider_class is None:
            logger.error(f"Provider not found: {name}")
            return None
        
        try:
            instance = provider_class(config)
            self._instances[name] = instance
            return instance
        except Exception as e:
            logger.error(f"Failed to create provider {name}: {e}")
            return None
    
    def get_provider(self, name: str) -> Optional[Any]:
        """Get an existing provider instance"""
        return self._instances.get(name)
    
    def list_providers(self) -> List[str]:
        """List all registered provider names"""
        return list(self._providers.keys())
    
    def unregister_provider(self, name: str) -> None:
        """Unregister a provider"""
        if name in self._providers:
            del self._providers[name]
        if name in self._instances:
            del self._instances[name]
        logger.info(f"Unregistered model provider: {name}")


class BrokerRegistry:
    """Registry for broker adapters"""
    
    def __init__(self):
        self._adapters: Dict[str, Type] = {}
        self._instances: Dict[str, Any] = {}
    
    def register_adapter(self, name: str, adapter_class: Type) -> None:
        """Register a broker adapter class"""
        self._adapters[name] = adapter_class
        logger.info(f"Registered broker adapter: {name}")
    
    def get_adapter_class(self, name: str) -> Optional[Type]:
        """Get a registered adapter class"""
        return self._adapters.get(name)
    
    def create_adapter(self, name: str, config: Dict[str, Any]) -> Optional[Any]:
        """Create an instance of an adapter"""
        adapter_class = self.get_adapter_class(name)
        if adapter_class is None:
            logger.error(f"Adapter not found: {name}")
            return None
        
        try:
            instance = adapter_class(config)
            self._instances[name] = instance
            return instance
        except Exception as e:
            logger.error(f"Failed to create adapter {name}: {e}")
            return None
    
    def get_adapter(self, name: str) -> Optional[Any]:
        """Get an existing adapter instance"""
        return self._instances.get(name)
    
    def list_adapters(self) -> List[str]:
        """List all registered adapter names"""
        return list(self._adapters.keys())
    
    def unregister_adapter(self, name: str) -> None:
        """Unregister an adapter"""
        if name in self._adapters:
            del self._adapters[name]
        if name in self._instances:
            del self._instances[name]
        logger.info(f"Unregistered broker adapter: {name}")


class DataProviderRegistry:
    """Registry for data providers"""
    
    def __init__(self):
        self._providers: Dict[str, Type] = {}
        self._instances: Dict[str, Any] = {}
    
    def register_provider(self, name: str, provider_class: Type) -> None:
        """Register a data provider class"""
        self._providers[name] = provider_class
        logger.info(f"Registered data provider: {name}")
    
    def get_provider_class(self, name: str) -> Optional[Type]:
        """Get a registered provider class"""
        return self._providers.get(name)
    
    def create_provider(self, name: str, config: Dict[str, Any]) -> Optional[Any]:
        """Create an instance of a provider"""
        provider_class = self.get_provider_class(name)
        if provider_class is None:
            logger.error(f"Provider not found: {name}")
            return None
        
        try:
            instance = provider_class(config)
            self._instances[name] = instance
            return instance
        except Exception as e:
            logger.error(f"Failed to create provider {name}: {e}")
            return None
    
    def get_provider(self, name: str) -> Optional[Any]:
        """Get an existing provider instance"""
        return self._instances.get(name)
    
    def list_providers(self) -> List[str]:
        """List all registered provider names"""
        return list(self._providers.keys())
    
    def unregister_provider(self, name: str) -> None:
        """Unregister a provider"""
        if name in self._providers:
            del self._providers[name]
        if name in self._instances:
            del self._instances[name]
        logger.info(f"Unregistered data provider: {name}")


# Global registry instances
model_registry = ModelRegistry()
broker_registry = BrokerRegistry()
data_provider_registry = DataProviderRegistry()
