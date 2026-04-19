from typing import List, Dict, Any
from unittest.mock import patch, MagicMock
from llmwiki import register_provider, BaseLLMProvider
from llmwiki.llm_client import LLMClient, _provider_registry
from llmwiki.config import settings

# Test custom provider implementation
class TestProvider(BaseLLMProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.custom_param = config.get('custom_param', 'default_value')

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        return f"Test response to: {messages[-1]['content']} (param: {self.custom_param}, temp: {temperature})"

def test_register_custom_provider():
    """Test registering a custom provider"""
    # Remove if already exists
    if 'test_provider' in _provider_registry:
        del _provider_registry['test_provider']

    register_provider('test_provider', TestProvider)
    assert 'test_provider' in _provider_registry
    assert _provider_registry['test_provider'] == TestProvider

def test_duplicate_provider_registration():
    """Test that registering duplicate provider names raises error"""
    if 'test_provider' in _provider_registry:
        del _provider_registry['test_provider']

    register_provider('test_provider', TestProvider)
    try:
        register_provider('test_provider', TestProvider)
        assert False, "Should have raised ValueError for duplicate provider"
    except ValueError as e:
        assert "already registered" in str(e)

def test_custom_provider_initialization():
    """Test initializing LLMClient with custom provider"""
    if 'test_provider' not in _provider_registry:
        register_provider('test_provider', TestProvider)

    # Test with custom config
    client = LLMClient(
        provider_name='test_provider',
        provider_config={
            'model': 'test-model-123',
            'custom_param': 'custom_value_456'
        }
    )

    assert isinstance(client.provider, TestProvider)
    assert client.provider.model == 'test-model-123'
    assert client.provider.custom_param == 'custom_value_456'

def test_custom_provider_chat_completion():
    """Test custom provider chat completion works"""
    if 'test_provider' not in _provider_registry:
        register_provider('test_provider', TestProvider)

    client = LLMClient(provider_name='test_provider')
    messages = [
        {"role": "user", "content": "Hello world"}
    ]
    response = client.chat_completion(messages, temperature=0.5)
    assert "Test response to: Hello world" in response
    assert "temp: 0.5" in response

@patch.dict('llmwiki.config.settings.custom_provider_configs', {
    'test_provider': {
        'custom_param': 'config_from_settings'
    }
})
def test_custom_provider_config_from_settings():
    """Test custom provider picks up config from settings"""
    if 'test_provider' not in _provider_registry:
        register_provider('test_provider', TestProvider)

    with patch('llmwiki.config.settings.llm_provider', 'test_provider'):
        client = LLMClient()
        assert client.provider.custom_param == 'config_from_settings'

def test_unknown_provider_error():
    """Test that unknown provider raises meaningful error"""
    try:
        LLMClient(provider_name='nonexistent_provider_12345')
        assert False, "Should have raised ValueError for unknown provider"
    except ValueError as e:
        assert "Unknown LLM provider" in str(e)
        assert "Available providers" in str(e)
