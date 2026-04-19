import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from llmwiki.auth import start_openai_device_flow, refresh_openai_token, get_valid_openai_token
from llmwiki.config import UserConfig

import pytest

@pytest.fixture(autouse=True)
def setup_test_config():
    """Setup isolated test config before each test"""
    tmp_dir = tempfile.TemporaryDirectory()
    original_config_dir = UserConfig._config_dir
    original_config_path = UserConfig._config_path

    # Override config path
    UserConfig._config_dir = Path(tmp_dir.name)
    UserConfig._config_path = UserConfig._config_dir / "config.json"

    yield

    # Restore original path
    UserConfig._config_dir = original_config_dir
    UserConfig._config_path = original_config_path
    tmp_dir.cleanup()

@patch('llmwiki.auth.requests.post')
@patch('llmwiki.auth.time.sleep')
def test_openai_device_flow_success(mock_sleep, mock_post):
    """Test successful OpenAI device flow authorization"""
    # Mock device code response
    mock_post.side_effect = [
        # First call: get device code
        MagicMock(
            status_code=200,
            json=lambda: {
                "device_code": "test_device_code",
                "user_code": "TEST-1234",
                "verification_uri_complete": "https://openai.com/activate?code=TEST1234",
                "expires_in": 600,
                "interval": 5
            }
        ),
        # Second call: polling, first pending
        MagicMock(
            status_code=400,
            json=lambda: {"error": "authorization_pending"}
        ),
        # Third call: polling, success
        MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "test_access_token_123",
                "refresh_token": "test_refresh_token_123",
                "expires_in": 3600
            }
        )
    ]

    # Run flow
    success = start_openai_device_flow()

    # Verify
    assert success == True
    assert UserConfig.get_openai_token() == "test_access_token_123"
    assert mock_post.call_count == 3

@patch('llmwiki.auth.requests.post')
def test_openai_device_flow_denied(mock_post):
    """Test user denies authorization"""
    mock_post.side_effect = [
        # Device code
        MagicMock(
            status_code=200,
            json=lambda: {
                "device_code": "test_device_code",
                "user_code": "TEST-1234",
                "verification_uri_complete": "https://openai.com/activate?code=TEST1234",
                "expires_in": 600,
                "interval": 5
            }
        ),
        # Denied
        MagicMock(
            status_code=400,
            json=lambda: {"error": "access_denied"}
        )
    ]

    success = start_openai_device_flow()
    assert success == False
    assert UserConfig.get_openai_token() is None

@patch('llmwiki.auth.requests.post')
def test_refresh_token_success(mock_post):
    """Test successful token refresh"""
    # Save existing tokens
    UserConfig.save_openai_token(
        access_token="old_access_token",
        refresh_token="test_refresh_token",
        expires_at=1234567890  # Expired
    )

    # Mock refresh response
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "access_token": "new_access_token_123",
            "refresh_token": "new_refresh_token_123",
            "expires_in": 3600
        }
    )

    success = refresh_openai_token()
    assert success == True
    assert UserConfig.get_openai_token() == "new_access_token_123"

@patch('llmwiki.auth.requests.post')
def test_get_valid_token_auto_refresh(mock_post):
    """Test get_valid_openai_token automatically refreshes expired tokens"""
    # Save expired token
    UserConfig.save_openai_token(
        access_token="old_access_token",
        refresh_token="test_refresh_token",
        expires_at=0  # Already expired
    )

    # Mock refresh response
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "access_token": "refreshed_token",
            "expires_in": 3600
        }
    )

    token = get_valid_openai_token()
    assert mock_post.called, "refresh endpoint was not called"
    assert token == "refreshed_token"
