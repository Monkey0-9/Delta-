"""
Template for creating custom model providers
Copy this file and modify for your custom provider
"""

from delta.models.base_provider import (
    BaseModelProvider, ModelMessage, ModelResponse, ModelCapabilities
)
from typing import Dict, Any, Optional, List, AsyncGenerator


class CustomModelProvider(BaseModelProvider):
    """Custom model provider template"""
    
    plugin_name = "custom_provider"
    plugin_version = "1.0.0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Add your custom initialization here
        self.custom_client = None
    
    async def initialize(self) -> bool:
        """Initialize your custom provider"""
        try:
            # Add your initialization logic here
            # For example, setting up API clients, loading models, etc.
            
            self._initialized = True
            return True
        except Exception as e:
            print(f"Failed to initialize custom provider: {e}")
            return False
    
    async def generate(self, messages: List[ModelMessage], 
                      params: Optional[Dict[str, Any]] = None) -> ModelResponse:
        """Generate response from your custom model"""
        if not self._initialized:
            raise RuntimeError("Provider not initialized")
        
        # Add your generation logic here
        # This should return a ModelResponse object
        
        import time
        start_time = time.time()
        
        # Example: Simple echo response
        content = messages[-1].content if messages else ""
        
        return ModelResponse(
            content=content,
            model=self.model_name,
            tokens_used=len(content.split()),
            finish_reason="stop",
            latency_ms=(time.time() - start_time) * 1000,
            metadata={}
        )
    
    async def generate_stream(self, messages: List[ModelMessage],
                            params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """Generate streaming response from your custom model"""
        if not self._initialized:
            raise RuntimeError("Provider not initialized")
        
        # Add your streaming logic here
        # This should yield content chunks
        
        content = messages[-1].content if messages else ""
        for char in content:
            yield char
    
    def get_capabilities(self) -> ModelCapabilities:
        """Define your model's capabilities"""
        return ModelCapabilities(
            max_context_tokens=4096,  # Adjust based on your model
            supports_function_calling=False,  # Adjust based on your model
            supports_streaming=True,  # Adjust based on your model
            supports_vision=False,  # Adjust based on your model
            estimated_cost_per_1k_tokens=0.0  # Adjust based on your model
        )
    
    def supports_function_calling(self) -> bool:
        """Return True if your model supports function calling"""
        return False
    
    async def shutdown(self) -> None:
        """Cleanup when provider is shut down"""
        # Add your cleanup logic here
        self._initialized = False


# To register this provider, add to your config.yaml:
# models:
#   - name: "my-custom-model"
#     provider: "custom"
#     endpoint: "your-endpoint"
#     model: "your-model-name"
#     enabled: true
#     params: {}

# Then register in your code:
# from delta.core.registry import model_registry
# from delta.plugins.models.custom_provider_template import CustomModelProvider
# model_registry.register_provider("custom", CustomModelProvider)
