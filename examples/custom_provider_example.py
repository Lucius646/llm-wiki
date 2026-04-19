"""
Example: How to add custom LLM providers to LLM Wiki

This example shows how to implement and register custom LLM providers
like Ollama (local LLMs) or OpenRouter (multi-model gateway).
"""

from typing import List, Dict, Any
import requests
from llmwiki import register_provider, BaseLLMProvider
from llmwiki.cli import cli

# -----------------------------------------------------------------------------
# Example 1: Ollama provider (local open-source LLMs)
# -----------------------------------------------------------------------------
class OllamaProvider(BaseLLMProvider):
    """Custom provider for Ollama local LLMs"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get('base_url', 'http://localhost:11434/api')
        self.timeout = config.get('timeout', 60)

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        url = f"{self.base_url}/chat"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }

        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()['message']['content']

# Register the Ollama provider
register_provider('ollama', OllamaProvider)

# -----------------------------------------------------------------------------
# Example 2: OpenRouter provider (access 100+ models from one API)
# -----------------------------------------------------------------------------
class OpenRouterProvider(BaseLLMProvider):
    """Custom provider for OpenRouter API"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        if not self.api_key:
            raise ValueError("OpenRouter API key is required, set it in .env as OPENROUTER_API_KEY")
        self.base_url = config.get('base_url', 'https://openrouter.ai/api/v1')

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

# Register the OpenRouter provider
register_provider('openrouter', OpenRouterProvider)

# -----------------------------------------------------------------------------
# Usage:
# 1. Add this to your .env file:
#    LLM_PROVIDER=ollama
#    MODEL_NAME=llama3:8b
#    CUSTOM_PROVIDER_CONFIGS='{"ollama": {"base_url": "http://localhost:11434/api"}}'
#
# OR for OpenRouter:
#    LLM_PROVIDER=openrouter
#    MODEL_NAME=anthropic/claude-3-opus
#    CUSTOM_PROVIDER_CONFIGS='{"openrouter": {"api_key": "sk-or-..."}}'
#
# 2. Run llmwiki as normal, it will automatically use your custom provider
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # You can also run the CLI directly with your custom providers loaded
    cli()
