"""
OpenAI-compatible API provider (covers OpenAI, Groq, Together, etc.)
"""

import httpx
import json
import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from delta.models.base_provider import (
    BaseModelProvider, OpenAICompatibleProvider, 
    ModelMessage, ModelResponse, ModelCapabilities
)

logger = logging.getLogger(__name__)


class OpenAICompatibleAPI(OpenAICompatibleProvider):
    """OpenAI-compatible API client for multiple providers"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client: Optional[httpx.AsyncClient] = None
        self.timeout = config.get("timeout", 60.0)
    
    async def initialize(self) -> bool:
        """Initialize the HTTP client"""
        try:
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
            self._initialized = True
            logger.info(f"Initialized OpenAI-compatible provider: {self.endpoint}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI-compatible provider: {e}")
            return False
    
    async def generate(self, messages: List[ModelMessage], 
                      params: Optional[Dict[str, Any]] = None) -> ModelResponse:
        """Generate a response from the model"""
        if not self.client:
            raise RuntimeError("Provider not initialized")
        
        # Merge default params with provided params
        generation_params = self.get_default_params()
        if params:
            generation_params.update(params)
        
        # Convert messages to API format
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            **generation_params
        }
        
        import time
        start_time = time.time()
        
        try:
            response = await self.client.post(
                f"{self.endpoint}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            
            latency_ms = (time.time() - start_time) * 1000
            data = response.json()
            
            # Extract response
            choice = data["choices"][0]
            content = choice["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
            finish_reason = choice.get("finish_reason", "stop")
            
            return ModelResponse(
                content=content,
                model=self.model_name,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
                latency_ms=latency_ms,
                metadata={"raw_response": data}
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in generate: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in generate: {e}")
            raise
    
    async def generate_stream(self, messages: List[ModelMessage],
                            params: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming response"""
        if not self.client:
            raise RuntimeError("Provider not initialized")
        
        generation_params = self.get_default_params()
        if params:
            generation_params.update(params)
        
        generation_params["stream"] = True
        
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            **generation_params
        }
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.endpoint}/chat/completions",
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in generate_stream: {e}")
            raise
        except Exception as e:
            logger.error(f"Error in generate_stream: {e}")
            raise
    
    def get_capabilities(self) -> ModelCapabilities:
        """Get model capabilities"""
        # Default capabilities for OpenAI-compatible models
        return ModelCapabilities(
            max_context_tokens=128000,  # Conservative default
            supports_function_calling=True,
            supports_streaming=True,
            supports_vision=False,
            estimated_cost_per_1k_tokens=0.002  # Conservative estimate
        )
    
    async def shutdown(self) -> None:
        """Shutdown the HTTP client"""
        if self.client:
            await self.client.aclose()
            self._initialized = False
            logger.info("OpenAI-compatible provider shutdown")


# Register the provider
from delta.core.registry import model_registry
model_registry.register_provider("openai-compatible", OpenAICompatibleAPI)
