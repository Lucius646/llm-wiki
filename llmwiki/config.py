import os
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
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

# Global settings instance
settings = Settings()
