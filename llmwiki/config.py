import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import Field, field_validator
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        protected_namespaces=('settings_',)
    )

    # LLM Configuration
    llm_provider: str = Field(default="openai", description="LLM provider: openai or anthropic")
    api_key: Optional[str] = Field(default=None, description="API key for the chosen LLM provider")
    model_name: str = Field(default="gpt-4o", description="Model name to use")

    # Wiki Configuration
    wiki_root: Path = Field(default_factory=Path.cwd, description="Root directory of the wiki")
    git_auto_commit: bool = Field(default=True, description="Enable automatic Git commits")

    # Audio Configuration
    whisper_model: str = Field(default="base", description="Whisper model for audio transcription")

    @field_validator("wiki_root")
    def validate_wiki_root(cls, v: Path) -> Path:
        """Ensure wiki root exists and is a directory"""
        if not v.exists():
            raise ValueError(f"Wiki root directory does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Wiki root is not a directory: {v}")
        return v

    @field_validator("llm_provider")
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider is supported"""
        if v.lower() not in ["openai", "anthropic"]:
            raise ValueError(f"Unsupported LLM provider: {v}. Supported providers: openai, anthropic")
        return v.lower()

    @property
    def raw_dir(self) -> Path:
        """Path to raw sources directory"""
        return self.wiki_root / "raw"

    @property
    def wiki_dir(self) -> Path:
        """Path to wiki pages directory"""
        return self.wiki_root / "wiki"

    @property
    def index_path(self) -> Path:
        """Path to index.md"""
        return self.wiki_dir / "index.md"

    @property
    def log_path(self) -> Path:
        """Path to log.md"""
        return self.wiki_dir / "log.md"

    def get_raw_topic_dir(self, topic: str) -> Path:
        """Get path to a topic directory in raw/"""
        return self.raw_dir / topic.lower().replace(" ", "-")

    def get_wiki_topic_dir(self, category: str, topic: str) -> Path:
        """Get path to a topic directory in wiki/"""
        return self.wiki_dir / category / topic.lower().replace(" ", "-")

class UserConfig:
    """Global user-level configuration stored in ~/.llmwiki/config.json"""
    _config_dir: Path = Path.home() / ".llmwiki"
    _config_path: Path = _config_dir / "config.json"

    @classmethod
    def _load(cls) -> Dict[str, Any]:
        """Load config from file, create default if not exists"""
        if not cls._config_path.exists():
            cls._config_dir.mkdir(exist_ok=True, parents=True)
            default_config = {
                "openai": {
                    "access_token": None,
                    "refresh_token": None,
                    "expires_at": None
                },
                "anthropic": {
                    "api_key": None
                }
            }
            cls._save(default_config)
            return default_config

        with open(cls._config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def _save(cls, config: Dict[str, Any]) -> None:
        """Save config to file"""
        with open(cls._config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    @classmethod
    def get_openai_token(cls) -> Optional[str]:
        """Get saved OpenAI access token"""
        config = cls._load()
        return config.get("openai", {}).get("access_token")

    @classmethod
    def save_openai_token(cls, access_token: str, refresh_token: str = None, expires_at: int = None) -> None:
        """Save OpenAI access token and optional refresh token/expiration time"""
        config = cls._load()
        if "openai" not in config:
            config["openai"] = {}
        config["openai"]["access_token"] = access_token
        if refresh_token is not None:
            config["openai"]["refresh_token"] = refresh_token
        if expires_at is not None:
            config["openai"]["expires_at"] = expires_at
        cls._save(config)

    @classmethod
    def get_anthropic_key(cls) -> Optional[str]:
        """Get saved Anthropic API key"""
        config = cls._load()
        return config.get("anthropic", {}).get("api_key")

    @classmethod
    def save_anthropic_key(cls, api_key: str) -> None:
        """Save Anthropic API key"""
        config = cls._load()
        if "anthropic" not in config:
            config["anthropic"] = {}
        config["anthropic"]["api_key"] = api_key
        cls._save(config)

    @classmethod
    def get_active_llm_credentials(cls) -> Optional[Dict[str, str]]:
        """Get credentials for the currently configured LLM provider"""
        if settings.llm_provider == "openai":
            token = cls.get_openai_token()
            if token:
                return {"access_token": token}
            # Fallback to API key if no OAuth token
            if settings.api_key:
                return {"api_key": settings.api_key}
        elif settings.llm_provider == "anthropic":
            key = cls.get_anthropic_key()
            if key:
                return {"api_key": key}
            if settings.api_key:
                return {"api_key": settings.api_key}
        return None

# Global settings instance
settings = Settings()
