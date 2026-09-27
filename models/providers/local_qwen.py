"""
Local Ollama/vLLM provider for zero-cost, private inference
"""

import httpx
import json
import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from delta.models.base_provider import (
    BaseModelProvider, LocalProvider,
    ModelMessage, ModelResponse, ModelCapabilities
)

logger = logging.getLogger(__name__)


class OllamaProvider(LocalProvider):
    """Ollama local model provider"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client: Optional[httpx.AsyncClient] = None
        self.timeout = config.get("timeout", 120.0)  # Longer timeout for local inference
    
    async def initialize(self) -> bool:
        """Initialize the Ollama client"""
        try:
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                base_url=self.get_endpoint()
            )
            
            # Test connection
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            
            self._initialized = True
            logger.info(f"Initialized Ollama provider at {self.get_endpoint()}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Ollama provider: {e}")
            return False
    
    async def generate(self, messages: List[ModelMessage], 
                      params: Optional[Dict[str, Any]] = None) -> ModelResponse:
        """Generate a response from the local model"""
        if not self.client:
            raise RuntimeError("Provider not initialized")
        
        # Convert messages to Ollama format
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "stream": False
        }
        
        if params:
            if "temperature" in params:
                payload["options"] = payload.get("options", {})
                payload["options"]["temperature"] = params["temperature"]
            if "num_predict" in params:
                payload["options"] = payload.get("options", {})
                payload["options"]["num_predict"] = params["num_predict"]
        
        import time
        start_time = time.time()
        
        try:
            response = await self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            
            latency_ms = (time.time() - start_time) * 1000
            data = response.json()
            
            # Extract response
            content = data.get("message", {}).get("content", "")
            tokens_used = data.get("eval_count", 0)
            finish_reason = "done"
            
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
        
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "stream": True
        }
        
        if params:
            if "temperature" in params:
                payload["options"] = payload.get("options", {})
                payload["options"]["temperature"] = params["temperature"]
        
        try:
            async with self.client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                content = data["message"].get("content", "")
                                if content:
                                    yield content
                            if "done" in data and data["done"]:
                                break
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
        return ModelCapabilities(
            max_context_tokens=32768,  # Typical for local models
            supports_function_calling=False,
            supports_streaming=True,
            supports_vision=False,
            estimated_cost_per_1k_tokens=0.0  # Free
        )
    
    async def shutdown(self) -> None:
        """Shutdown the HTTP client"""
        if self.client:
            await self.client.aclose()
            self._initialized = False
            logger.info("Ollama provider shutdown")


class VLLMProvider(LocalProvider):
    """vLLM local model provider"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client: Optional[httpx.AsyncClient] = None
        self.timeout = config.get("timeout", 120.0)
    
    async def initialize(self) -> bool:
        """Initialize the vLLM client"""
        try:
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                base_url=self.get_endpoint()
            )
            
            # Test connection
            response = await self.client.get("/health")
            response.raise_for_status()
            
            self._initialized = True
            logger.info(f"Initialized vLLM provider at {self.get_endpoint()}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize vLLM provider: {e}")
            return False
    
    async def generate(self, messages: List[ModelMessage], 
                      params: Optional[Dict[str, Any]] = None) -> ModelResponse:
        """Generate a response from the local model"""
        if not self.client:
            raise RuntimeError("Provider not initialized")
        
        # Convert messages to vLLM format (OpenAI-compatible)
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "stream": False
        }
        
        if params:
            payload.update(params)
        
        import time
        start_time = time.time()
        
        try:
            response = await self.client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
            
            latency_ms = (time.time() - start_time) * 1000
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
            finish_reason = data["choices"][0].get("finish_reason", "stop")
            
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
        
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "stream": True
        }
        
        if params:
            payload.update(params)
        
        try:
            async with self.client.stream("POST", "/v1/chat/completions", json=payload) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
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
        return ModelCapabilities(
            max_context_tokens=32768,
            supports_function_calling=True,
            supports_streaming=True,
            supports_vision=False,
            estimated_cost_per_1k_tokens=0.0
        )
    
    async def shutdown(self) -> None:
        """Shutdown the HTTP client"""
        if self.client:
            await self.client.aclose()
            self._initialized = False
            logger.info("vLLM provider shutdown")


# Register the providers
from delta.core.registry import model_registry
model_registry.register_provider("ollama", OllamaProvider)
model_registry.register_provider("vllm", VLLMProvider)
